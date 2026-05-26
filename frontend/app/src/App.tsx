import { useEffect, useState } from "react";
import type { SyntheticEvent } from "react";
import { useGameStore } from "./store/gameStore";
import "./styles/global.css";
import { AuthPanel } from "./components/AuthPanel";
import type { AuthMode } from "./components/AuthPanel";
import { ActionPanel } from "./components/ActionPanel";
import { WorldMap } from "./components/WorldMap";
const SPEECH_ROTATE_MS = 5000;
function App() {
  const user = useGameStore((state) => state.user);
  const world = useGameStore((state) => state.world);
  const status = useGameStore((state) => state.status);
  const isSubmitting = useGameStore((state) => state.isSubmitting);
  const isBusy = useGameStore((state) => state.isBusy);
  const runStep = useGameStore((state) => state.runStep);
  const resetWorld = useGameStore((state) => state.resetWorld);
  const checkAuth = useGameStore((state) => state.checkAuth);
  const login = useGameStore((state) => state.login);
  const register = useGameStore((state) => state.register);
  const logout = useGameStore((state) => state.logout);

  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("test01");
  const [password, setPassword] = useState("123456");
  const [affair, setAffair] = useState("");
  const [selectedActorId, setSelectedActorId] = useState<string | null>(null);
  const actors = world?.actors ?? [];
  const speakingActors = actors.filter((actor) => actor.last_speech?.trim());
  const selectedActor = actors.find((actor) => actor.actor_id === selectedActorId) ?? null;
  const [activeSpeechIndex, setActiveSpeechIndex] = useState(0);
  const activeSpeechActor =
    activeSpeechIndex >= 0 && activeSpeechIndex < speakingActors.length
      ? speakingActors[activeSpeechIndex % speakingActors.length]
      : null;
  const speechQueueKey = speakingActors
    .map((actor) => `${actor.actor_id}:${actor.last_speech}`)
    .join("|");
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    setActiveSpeechIndex(speakingActors.length > 0 ? 0 : -1);
  }, [speechQueueKey]);

  useEffect(() => {
    if (
      activeSpeechIndex < 0 ||
      speakingActors.length === 0 ||
      activeSpeechIndex >= speakingActors.length - 1
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      setActiveSpeechIndex((current) => {
        const next = current + 1;
        return Math.min(next, speakingActors.length - 1);
      });
    }, SPEECH_ROTATE_MS);

    return () => window.clearTimeout(timer);
  }, [activeSpeechIndex, speakingActors.length, speechQueueKey]);

  async function handleSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!username.trim() || !password.trim()) {
      return;
    }

    if (authMode === "login") {
      await login({ username, password });
    } else {
      await register({ username, password });
    }
  }

  async function handleLogout() {
    await logout();
  }
  async function handleRunStep() {
  await runStep(affair);
  setAffair("");
}

async function handleResetWorld() {
  await resetWorld();
}

  if (!user) {
    return (
      <AuthPanel
        authMode={authMode}
        username={username}
        password={password}
        status={status}
        isSubmitting={isSubmitting}
        onAuthModeChange={setAuthMode}
        onUsernameChange={setUsername}
        onPasswordChange={setPassword}
        onSubmit={handleSubmit}
      />
    );
  }

  return (
    <main className="app-shell">
      <section className="mobile-frame">
        <header className="app-header">
          <div>
            <p className="app-kicker">{world?.company?.name || "熊心壮职"}</p>
            <h1>入职第一天</h1>
          </div>
          <button className="icon-button" type="button" onClick={handleLogout}>
            退
          </button>
        </header>

        <WorldMap
          world={world}
          actors={actors}
          activeSpeechActor={activeSpeechActor}
          selectedActorId={selectedActorId}
          onSelectActor={setSelectedActorId}
        />
        <ActionPanel
          user={user}
          world={world}
          status={status}
          affair={affair}
          isBusy={isBusy}
          selectedActor={selectedActor}
          onAffairChange={setAffair}
          onRunStep={handleRunStep}
          onResetWorld={handleResetWorld}
          onCloseActor={() => setSelectedActorId(null)}
        />
      </section>
    </main>
  );
}

export default App;
