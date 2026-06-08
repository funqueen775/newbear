"""记忆系统集成测试"""
import sys
sys.path.insert(0, ".")

from src.core.world.runtime_state import (
    ActorRuntimeState, CompanyRuntimeState, MemoryRecord,
    RelationshipRecord, WorldRuntimeState,
)
from src.core.world.memory_engine import (
    append_actor_memory, estimate_importance,
    _evict_lowest_importance, _is_duplicate, write_step_memories,
)
from src.core.world.memory_retriever import (
    retrieve_relevant_memories, retrieve_causal_chain, KIND_WEIGHT,
)

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


def make_world():
    company = CompanyRuntimeState(name="TestCo")
    actors = {
        "a1": ActorRuntimeState(actor_id="a1", display_name="Alice", location="office"),
        "a2": ActorRuntimeState(actor_id="a2", display_name="Bob", location="office"),
        "a3": ActorRuntimeState(actor_id="a3", display_name="Charlie", location="meeting"),
    }
    return WorldRuntimeState(company=company, actors=actors)


# --- Test 1: Basic memory write and memory_texts ---
print("\n[Test 1] Basic memory write and memory_texts property")
world = make_world()
append_actor_memory(world, actor_id="a1", kind="observation", text="hello", clock="09:00")
check("memory_stream has 1 item", len(world.actors["a1"].memory_stream) == 1)
check("memory_texts returns ['hello']", world.actors["a1"].memory_texts == ["hello"])
check("no .memory attribute", not hasattr(world.actors["a1"], "memory"))


# --- Test 2: Importance estimation ---
print("\n[Test 2] Importance estimation")
check("observation importance", estimate_importance("test", "observation") == 1)
check("meeting importance", estimate_importance("test", "meeting") == 5)
check("reflection importance", estimate_importance("test", "reflection") == 6)
check("incident importance", estimate_importance("test", "incident") == 7)
check("pantry importance", estimate_importance("test", "pantry") == 4)


# --- Test 3: Eviction by importance ---
print("\n[Test 3] Eviction by importance")
world = make_world()
for i in range(130):
    kind = "observation" if i < 120 else "incident"
    append_actor_memory(world, actor_id="a1", kind=kind, text=f"memory {i}", clock="09:00")
stream = world.actors["a1"].memory_stream
check(f"stream capped at 120 (got {len(stream)})", len(stream) <= 120)
check("high-importance incident memories survived", any(m.kind == "incident" for m in stream))


# --- Test 4: Deduplication ---
print("\n[Test 4] Deduplication")
world = make_world()
append_actor_memory(world, actor_id="a1", kind="observation", text="I saw Bob working on the project", clock="09:00")
count_before = len(world.actors["a1"].memory_stream)
append_actor_memory(world, actor_id="a1", kind="observation", text="I saw Bob working on the project", clock="09:00")
count_after = len(world.actors["a1"].memory_stream)
check("duplicate was rejected", count_after == count_before)

append_actor_memory(world, actor_id="a1", kind="observation", text="Completely different event happened today", clock="09:00")
check("different text was accepted", len(world.actors["a1"].memory_stream) == count_before + 1)

append_actor_memory(world, actor_id="a1", kind="reflection", text="I saw Bob working on the project", clock="09:00")
check("reflection bypasses dedup", len(world.actors["a1"].memory_stream) == count_before + 2)


# --- Test 5: Retrieval with KIND_WEIGHT ---
print("\n[Test 5] Retrieval with kind weight")
world = make_world()
append_actor_memory(world, actor_id="a1", kind="observation", text="test observation", clock="09:00")
append_actor_memory(world, actor_id="a1", kind="reflection", text="test reflection", clock="09:00")
append_actor_memory(world, actor_id="a1", kind="meeting", text="test meeting", clock="09:00")
results = retrieve_relevant_memories(world.actors["a1"], query="test", limit=3)
check("retrieval returns results", len(results) == 3)
check("kind-weighted ranking works (meeting or reflection first)", results[0] in ("test reflection", "test meeting"))


# --- Test 6: Archived memories get lower weight ---
print("\n[Test 6] Archived memory weight")
world = make_world()
append_actor_memory(world, actor_id="a1", kind="observation", text="archived event", clock="09:00")
append_actor_memory(world, actor_id="a1", kind="observation", text="fresh event", clock="09:00")
world.actors["a1"].memory_stream[0].archived = True
results = retrieve_relevant_memories(world.actors["a1"], query="event", limit=2)
check("fresh ranked higher than archived", results[0] == "fresh event")


# --- Test 7: Relationship system ---
print("\n[Test 7] Relationship system")
world = make_world()
check("initially no relationships", len(world.actors["a1"].relationships) == 0)

reactions = [
    {"actor_id": "a1", "display_name": "Alice", "to_location": "office", "task": "coding", "speech": "I am working"},
    {"actor_id": "a2", "display_name": "Bob", "to_location": "office", "task": "review", "speech": "Looks good to me"},
]
write_step_memories(world, clock="09:00", affair="", actor_reactions=reactions, encounter_records=[])
check("relationship a1->a2 created", "a2" in world.actors["a1"].relationships)
check("interaction count > 0", world.actors["a1"].relationships["a2"].interaction_count > 0)
check("trust > 50 (positive interaction)", world.actors["a1"].relationships["a2"].trust > 50)


# --- Test 8: Causal chain infrastructure ---
print("\n[Test 8] Causal chain infrastructure")
world = make_world()
append_actor_memory(world, actor_id="a1", kind="observation", text="cause event", clock="09:00")
append_actor_memory(world, actor_id="a1", kind="reflection", text="effect event", clock="09:00")
world.actors["a1"].memory_stream[1].caused_by_id = world.actors["a1"].memory_stream[0].memory_id
chain = retrieve_causal_chain(world.actors["a1"], world.actors["a1"].memory_stream[1].memory_id)
check("causal chain has 2 items", len(chain) == 2)
check("chain starts with cause", chain[0] == "cause event")
check("chain ends with effect", chain[1] == "effect event")


# --- Test 9: Full step simulation ---
print("\n[Test 9] Full step simulation (write_step_memories)")
world = make_world()
reactions = [
    {"actor_id": "a1", "display_name": "Alice", "to_location": "office", "task": "fix bug", "speech": "working on it"},
    {"actor_id": "a2", "display_name": "Bob", "to_location": "office", "task": "review PR", "speech": "LGTM"},
    {"actor_id": "a3", "display_name": "Charlie", "to_location": "meeting", "task": "prepare slides", "speech": "almost done"},
]
write_step_memories(world, clock="10:00", affair="ship feature X", actor_reactions=reactions, encounter_records=[])

a1 = world.actors["a1"]
a3 = world.actors["a3"]
check("a1 has memories", len(a1.memory_stream) > 0)
check("a1 has user_input memory", any(m.kind == "user_input" for m in a1.memory_stream))
check("a1 observed Bob (same location)", any("Bob" in m.text for m in a1.memory_stream))
check("a3 did NOT observe Bob (different location)", not any("Bob" in m.text for m in a3.memory_stream))
check("a1 has relationship with a2", "a2" in a1.relationships)


# --- Summary ---
print(f"\n{'='*40}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    print("SOME TESTS FAILED!")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
