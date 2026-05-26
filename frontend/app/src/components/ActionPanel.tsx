import type { ActorState, AuthUser, WorldState } from "../types/api";
import { ActorDetailPanel } from "./ActorDetailPanel";

type ActionPanelProps = {
  user: AuthUser;
  world: WorldState | null;
  status: string;
  affair: string;
  isBusy: boolean;
  selectedActor: ActorState | null;
  onAffairChange: (value: string) => void;
  onRunStep: () => void;
  onResetWorld: () => void;
  onCloseActor: () => void;
};

export function ActionPanel({
  user,
  world,
  status,
  affair,
  isBusy,
  selectedActor,
  onAffairChange,
  onRunStep,
  onResetWorld,
  onCloseActor,
}: ActionPanelProps) {
  return (
    <section className="bottom-panel">
      {selectedActor ? (
        <ActorDetailPanel actor={selectedActor} onClose={onCloseActor} />
      ) : null}

      <div className="status-row">
        <span>{status}</span>
        <span>{user.username}</span>
        <span>{world?.company?.clock || "09:00"}</span>
        <span>CNY {world?.company?.cash ?? 5000}</span>
      </div>

      <label className="input-box">
        <span>你想对同事说什么？</span>
        <input
          value={affair}
          onChange={(event) => onAffairChange(event.target.value)}
          placeholder="例如：我先了解一下大家手头的任务"
        />
      </label>

      <div className="action-row">
        <button type="button" onClick={onRunStep} disabled={isBusy}>
          {isBusy ? "推进中..." : "推进 30 分钟"}
        </button>

        <button
          className="secondary-button"
          type="button"
          onClick={onResetWorld}
          disabled={isBusy}
        >
          重置世界
        </button>
      </div>
    </section>
  );
}