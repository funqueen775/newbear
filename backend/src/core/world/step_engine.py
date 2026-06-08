from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from src.core.map.map_semantics import normalize_location_name
from src.core.world.actor_reactions import build_actor_reaction
from src.core.world.dialogue_engine import decide_dialogues, generate_dialogues
from src.core.world.encounter_engine import find_encounter_groups
from src.core.world.runtime_state import EncounterRecord, UserInputRecord, WorldRuntimeState
from src.core.world.incident_engine import trigger_incident_for_clock
from src.core.world.meeting_engine import trigger_meeting_for_clock
from src.core.world.memory_engine import write_step_memories
from src.core.world.memory_retriever import retrieve_relevant_memories
from src.core.world.pantry_engine import trigger_pantry_for_clock
from src.core.world.report_engine import trigger_report_for_clock



STEP_MINUTES = 30


def advance_clock(clock: str) -> str:
    """把 HH:MM 时间往后推进 30 分钟。"""

    hour_text, minute_text = clock.split(":")
    hour = int(hour_text)
    minute = int(minute_text)

    minute += STEP_MINUTES

    if minute >= 60:
        hour += 1
        minute -= 60

    return f"{hour:02d}:{minute:02d}"


def run_one_step(world: WorldRuntimeState, affair: str = "") -> WorldRuntimeState:
    run_prepare_phase(world, affair=affair)
    run_settle_phase(world, affair=affair)
    return world


def run_prepare_phase(world: WorldRuntimeState, affair: str = "") -> WorldRuntimeState:
    actor_items = list(world.actors.values())
    incident_payload = None
    if world.pending_incident is not None:
        incident_payload = {
            "incident_id": world.pending_incident.incident_id,
            "time": world.pending_incident.time,
            "title": world.pending_incident.title,
            "content": world.pending_incident.content,
        }

    query_text = affair
    if incident_payload:
        query_text = "\n".join(
            [
                str(affair or ""),
                str(incident_payload.get("title", "")),
                str(incident_payload.get("content", "")),
            ]
        )

    with ThreadPoolExecutor(max_workers=max(1, len(actor_items))) as executor:
        reaction_by_actor_id = {
            actor.actor_id: reaction
            for actor, reaction in zip(
                actor_items,
                executor.map(
                    lambda actor: build_actor_reaction(
                        actor.actor_id,
                        affair,
                        clock=world.company.clock,
                        memories=retrieve_relevant_memories(
                            actor,
                            query=query_text,
                            limit=6,
                        ),
                        incident=incident_payload,
                    ),
                    actor_items,
                ),
            )
        }

    for actor in actor_items:
        reaction = reaction_by_actor_id[actor.actor_id]

        actor.current_task = str(reaction["task"])
        actor.intent = str(reaction.get("intent", ""))
        actor.move_to = str(reaction.get("move_to", actor.location))
        actor.last_speech = str(reaction["speech"])
        actor.pending_action = {
            "affair": affair,
            "task": actor.current_task,
            "intent": actor.intent,
            "move_to": actor.move_to,
            "speech": actor.last_speech,
            "stress_delta": int(reaction["stress_delta"]),
            "energy_delta": int(reaction["energy_delta"]),
            "provider": str(reaction.get("provider", "unknown")),
        }

    return world


def run_settle_phase(world: WorldRuntimeState, affair: str = "") -> WorldRuntimeState:
    old_clock = world.company.clock
    actor_reactions: list[dict[str, object]] = []
    action_by_actor_id: dict[str, dict[str, object]] = {}

    for actor in world.actors.values():
        action = actor.pending_action or {}
        action_by_actor_id[actor.actor_id] = action

        stress_delta = int(action.get("stress_delta", 0))
        energy_delta = int(action.get("energy_delta", -2))
        provider = str(action.get("provider", "unknown"))

        from_location = actor.location
        target_location = normalize_location_name(
            str(action.get("move_to") or actor.move_to or actor.location)
        )

        actor.location = target_location
        actor.move_to = target_location

        actor.energy = max(0, actor.energy + energy_delta)
        actor.stress = min(100, max(0, actor.stress + stress_delta))

        actor_reactions.append(
            {
                "actor_id": actor.actor_id,
                "display_name": actor.display_name,
                "from_location": from_location,
                "to_location": actor.location,
                "task": actor.current_task,
                "intent": actor.intent,
                "move_to": actor.move_to,
                "speech": actor.last_speech,
                "stress": actor.stress,
                "energy": actor.energy,
                "provider": provider,
                "location": action.get("from_location", actor.location),
                "to_location": actor.location,

            }
        )

    encounter_groups = find_encounter_groups(world)

    dialogue_decisions = decide_dialogues(
        clock=old_clock,
        affair=affair,
        encounter_groups=encounter_groups,
    )

    actor_snapshots = [
        {
            "actor_id": actor.actor_id,
            "display_name": actor.display_name,
            "location": actor.location,
            "intent": actor.intent,
            "task": actor.current_task,
            "speech": actor.last_speech,
            "memory": actor.memory_texts[-5:],
        }
        for actor in world.actors.values()
    ]

    generated_dialogues = generate_dialogues(
        clock=old_clock,
        affair=affair,
        conversations=dialogue_decisions,
        actors=actor_snapshots,
    )

    for conversation in generated_dialogues:
        for line in conversation.get("lines", []):
            actor_id = str(line.get("actor_id", ""))
            speech = str(line.get("speech", "") or "").strip()

            if actor_id not in world.actors or not speech:
                continue

            world.actors[actor_id].last_speech = speech

    encounters: list[EncounterRecord] = []

    for conversation in generated_dialogues:
        location = str(conversation.get("location", ""))
        actor_ids = [str(actor_id) for actor_id in conversation.get("actor_ids", [])]
        actor_names = [
            world.actors[actor_id].display_name
            for actor_id in actor_ids
            if actor_id in world.actors
        ]
        lines = conversation.get("lines", [])

        if len(actor_ids) < 2 or not lines:
            continue

        summary = f"{'、'.join(actor_names)}在{location}围绕当前事务进行了对话"

        encounter = EncounterRecord(
            encounter_id=len(world.encounters) + len(encounters) + 1,
            location=location,
            actor_ids=actor_ids,
            actor_names=actor_names,
            summary=summary,
            day=world.company.day,
            step=world.company.step,
            clock=old_clock,
            dialogue=lines,
        )

        encounters.append(encounter)

    world.encounters.extend(encounters)

    for reaction in actor_reactions:
        actor_id = str(reaction["actor_id"])
        actor = world.actors.get(actor_id)
        if actor is not None:
            reaction["speech"] = actor.last_speech

    for actor in world.actors.values():
        action = action_by_actor_id.get(actor.actor_id, {})

        actor.pending_action = {}

    world.company.step += 1
    world.company.clock = advance_clock(world.company.clock)
    trigger_pantry_for_clock(world, world.company.clock)
    world.company.phase = "prepare"
    triggered_meeting = trigger_meeting_for_clock(world, world.company.clock)
    triggered_incident = None

    if triggered_meeting is None:
        triggered_incident = trigger_incident_for_clock(world, world.company.clock)


    raw_affair = str(affair or "")
    world.user_inputs.append(
        UserInputRecord(
            input_id=len(world.user_inputs) + 1,
            raw_text=raw_affair,
            is_empty=not bool(raw_affair.strip()),
            day=world.company.day,
            step=world.company.step,
            clock=world.company.clock,
            actor_reactions=actor_reactions,
        )
    )
    write_step_memories(
        world,
        clock=old_clock,
        affair=affair,
        actor_reactions=actor_reactions,
        encounter_records=encounters,
        incident=triggered_incident,
    )


    world.company.logs.append(
        {
            "type": "step",
            "from_clock": old_clock,
            "to_clock": world.company.clock,
            "day": world.company.day,
            "step": world.company.step,
            "affair": affair,
            "actor_reactions": actor_reactions,
            "encounters": [
                {
                    "encounter_id": encounter.encounter_id,
                    "location": encounter.location,
                    "actor_ids": encounter.actor_ids,
                    "actor_names": encounter.actor_names,
                    "summary": encounter.summary,
                    "day": encounter.day,
                    "step": encounter.step,
                    "clock": encounter.clock,
                    "dialogue": encounter.dialogue,
                }
                for encounter in encounters
            ],
            "incident": (
                {
                    "incident_id": triggered_incident.incident_id,
                    "time": triggered_incident.time,
                    "title": triggered_incident.title,
                    "content": triggered_incident.content,
                }
                if triggered_incident
                else None
            ),
            "meeting": (
                {
                    "meeting_id": triggered_meeting.meeting_id,
                    "time": triggered_meeting.time,
                    "title": triggered_meeting.title,
                    "content": triggered_meeting.content,
                    "participants": triggered_meeting.participants,
                }
                if triggered_meeting
                else None
            ),


        }
    )

    trigger_report_for_clock(world, world.company.clock)

    return world
