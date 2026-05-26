import type { CSSProperties } from "react";
import type { ActorState, MapLocation, WorldState } from "../types/api";

const MAP_IMAGE_SRC = "/assets/map_slices/map_layer_001_-1.png";
const SPEECH_BUBBLE_WIDTH = 170;

const ACTOR_COLORS: Record<string, string> = {
  xionglaoban: "#6f4a2f",
  xiongjishu: "#3f5568",
  xiongshichang: "#4f7d4f",
  xiongxingzheng: "#9a6a45",
};

const ACTOR_ASSETS: Record<string, string> = {
  xionglaoban: "/assets/actors/xionglaoban/idle_front.webp",
  xiongjishu: "/assets/actors/xiongjishu/idle_front.webp",
  xiongshichang: "/assets/actors/xiongshichang/idle_front.webp",
  xiongxingzheng: "/assets/actors/xiongxingzheng/idle_front.webp",
};

type SpeechPlacement = "above" | "below";

type SpeechPosition = {
  x: number;
  y: number;
  placement: SpeechPlacement;
};

type WorldMapProps = {
  world: WorldState | null;
  actors: ActorState[];
  activeSpeechActor: ActorState | null;
  selectedActorId: string | null;
  onSelectActor: (actorId: string) => void;
};

function getActorAsset(actorId: string) {
  return ACTOR_ASSETS[actorId] || ACTOR_ASSETS.xionglaoban;
}

function getActorFormationOffset(index: number, total: number) {
  if (total <= 1) {
    return { x: 0, y: 0 };
  }

  const spacingX = 38;
  const spacingY = 10;
  const center = (total - 1) / 2;

  return {
    x: (index - center) * spacingX,
    y: (index % 2 === 0 ? -1 : 1) * spacingY,
  };
}

function getSpeechFormationOffset(index: number, total: number, anchorLeft: number) {
  const center = (total - 1) / 2;
  const row = index % 2;
  let edgeShift = 0;

  if (anchorLeft < 24) {
    edgeShift = 78;
  } else if (anchorLeft > 76) {
    edgeShift = -78;
  }

  return {
    x: edgeShift + (index - center) * SPEECH_BUBBLE_WIDTH,
    y: -88 - row * 70,
  };
}

function getSpeechBubblePosition(
  left: number,
  top: number,
  index: number,
  total: number,
): SpeechPosition {
  const offset = getSpeechFormationOffset(index, total, left);

  if (top < 28) {
    return {
      ...offset,
      y: 72 + (index % 2) * 54,
      placement: "below",
    };
  }

  return {
    ...offset,
    placement: "above",
  };
}

function getLocationPosition(
  location: MapLocation,
  world: WorldState | null,
) {
  if (!location.anchor_x || !location.anchor_y) {
    return null;
  }

  const pixelWidth = world?.map?.world?.pixel_width || 1;
  const pixelHeight = world?.map?.world?.pixel_height || 1;

  return {
    left: (location.anchor_x / pixelWidth) * 100,
    top: (location.anchor_y / pixelHeight) * 100,
  };
}

export function WorldMap({
  world,
  actors,
  activeSpeechActor,
  selectedActorId,
  onSelectActor,
}: WorldMapProps) {
  const mapLocations = world?.map?.semantics?.locations ?? [];
  const locationByName = new Map(mapLocations.map((location) => [location.name, location]));
  const actorsByLocation = new Map<string, ActorState[]>();

  for (const actor of actors) {
    const group = actorsByLocation.get(actor.location) ?? [];
    group.push(actor);
    actorsByLocation.set(actor.location, group);
  }

  return (
    <section className="scene-panel">
      <div className="world-map">
        <img className="world-map-image" src={MAP_IMAGE_SRC} alt="公司地图" />

        <div className="speech-layer">
          {activeSpeechActor ? (() => {
            const actor = activeSpeechActor;
            const location = locationByName.get(actor.location);

            if (!location) {
              return null;
            }

            const position = getLocationPosition(location, world);

            if (!position) {
              return null;
            }

            const color = ACTOR_COLORS[actor.actor_id] || "#18212f";
            const group = actorsByLocation.get(actor.location) ?? [];
            const actorIndex = group.findIndex(
              (item) => item.actor_id === actor.actor_id,
            );
            const speechPosition = getSpeechBubblePosition(
              position.left,
              position.top,
              actorIndex,
              group.length,
            );

            return (
              <div
                className={`floor-speech ${
                  speechPosition.placement === "below" ? "is-below" : ""
                }`}
                key={`${actor.actor_id}-speech`}
                style={{
                  "--speech-anchor-x": `${position.left}%`,
                  "--speech-anchor-y": `${position.top}%`,
                  zIndex: 40,
                  borderColor: color,
                  "--speech-offset-x": `${speechPosition.x}px`,
                  "--speech-offset-y": `${speechPosition.y}px`,
                } as CSSProperties}
              >
                <strong style={{ color }}>{actor.display_name}</strong>
                <span>{actor.last_speech}</span>
              </div>
            );
          })() : null}
        </div>

        <div className="actor-layer">
          {actors.map((actor, index) => {
            const location = locationByName.get(actor.location);

            if (!location) {
              return null;
            }

            const position = getLocationPosition(location, world);

            if (!position) {
              return null;
            }

            const color = ACTOR_COLORS[actor.actor_id] || "#18212f";
            const group = actorsByLocation.get(actor.location) ?? [];
            const actorIndex = group.findIndex(
              (item) => item.actor_id === actor.actor_id,
            );
            const formation = getActorFormationOffset(actorIndex, group.length);

            return (
              <button
                className={`actor-marker ${
                  selectedActorId === actor.actor_id ? "is-selected" : ""
                }`}
                key={actor.actor_id}
                style={{
                  left: `${position.left}%`,
                  top: `${position.top}%`,
                  zIndex: 10 + index,
                  "--actor-offset-x": `${formation.x}px`,
                  "--actor-offset-y": `${formation.y}px`,
                } as CSSProperties}
                type="button"
                onClick={() => onSelectActor(actor.actor_id)}
                title={`${actor.display_name} · ${actor.location}`}
              >
                <div className="floor-actor-body">
                  <div className="floor-actor-shadow" />
                  <img
                    className="floor-actor-image"
                    src={getActorAsset(actor.actor_id)}
                    alt={actor.display_name}
                  />
                  <div
                    className="floor-actor-label"
                    style={{ color, borderColor: color }}
                  >
                    {actor.display_name}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}