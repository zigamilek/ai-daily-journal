import { useEffect, useMemo, useState } from "react";
import { api, type JournalTree, type ProposalResponse } from "../api";
import { DiffViewer } from "../components/DiffViewer";
import { SidebarTree } from "../components/SidebarTree";
import { WriteComposer } from "../components/WriteComposer";

type Me = { id: number; email: string; timezone: string };

function randomKey() {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function AppShell() {
  const [me, setMe] = useState<Me | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [tree, setTree] = useState<JournalTree>([]);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [proposal, setProposal] = useState<ProposalResponse | null>(null);
  const [lastInputText, setLastInputText] = useState("");
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [latest, treeResp] = await Promise.all([api.latest(), api.tree()]);
    setTree(treeResp.tree);
    setSelectedDay(latest.day_date);
    setContent(latest.content);
  }

  async function boot() {
    try {
      const user = await api.me();
      setMe(user);
      await refresh();
    } catch {
      setMe(null);
    }
  }

  useEffect(() => {
    void boot();
  }, []);

  async function loadDay(day: string) {
    const file = await api.dayFile(day);
    setSelectedDay(day);
    setContent(file.content);
  }

  async function onPropose(text: string, instruction?: string) {
    try {
      setError(null);
      setLastInputText(text);
      const next = await api.propose(text, proposal?.session_id, instruction);
      setProposal(next);
    } catch (err) {
      setError(String(err));
    }
  }

  async function onConfirm() {
    if (!proposal) return;
    const response = await api.confirm(proposal.session_id, randomKey());
    setProposal(null);
    setSelectedDay(response.day_date);
    setContent(response.final_content);
    await refresh();
  }

  async function onCancel() {
    if (!proposal) return;
    await api.cancel(proposal.session_id);
    setProposal(null);
    setRevisionInstruction("");
  }

  async function onRevise() {
    if (!proposal) return;
    const baseText = lastInputText || proposal.proposed_entries.at(-1)?.source_user_text || "";
    if (!baseText.trim()) return;
    const next = await api.propose(baseText, proposal.session_id, revisionInstruction || undefined);
    setProposal(next);
    setRevisionInstruction("");
  }

  const dayTitle = useMemo(() => selectedDay ?? "Brez izbranega dne", [selectedDay]);

  if (!me) {
    return (
      <main className="auth-shell">
        <h1>AI Daily Journal</h1>
        <p>Prijava ali registracija</p>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Geslo"
          type="password"
        />
        <div className="auth-actions">
          <button
            onClick={async () => {
              await api.register(email, password, "Europe/Ljubljana");
              await api.login(email, password);
              await boot();
            }}
          >
            Registracija
          </button>
          <button
            onClick={async () => {
              await api.login(email, password);
              await boot();
            }}
          >
            Prijava
          </button>
        </div>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <SidebarTree tree={tree} selectedDay={selectedDay} onSelectDay={(d) => void loadDay(d)} />
      <main className="main-panel">
        <header>
          <h1>AI Daily Journal</h1>
          <p className="muted">{me.email}</p>
        </header>
        <WriteComposer onPropose={onPropose} />
        {error && <p className="error">{error}</p>}
        {proposal && (
          <section className="proposal">
            <h3>Predlog ({proposal.action})</h3>
            <p>{proposal.reason}</p>
            <DiffViewer diffText={proposal.diff_text} />
            {(proposal as ProposalResponse & { warnings?: string[] }).warnings?.length ? (
              <ul className="warning-list">
                {(proposal as ProposalResponse & { warnings?: string[] }).warnings?.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
            <input
              value={revisionInstruction}
              onChange={(e) => setRevisionInstruction(e.target.value)}
              placeholder="Navodilo za popravek (npr. bolj jedrnato)"
            />
            <div className="row">
              <button onClick={() => void onConfirm()}>Potrdi</button>
              <button onClick={() => void onRevise()}>Zahtevaj spremembe</button>
              <button onClick={() => void onCancel()}>Prekliči</button>
            </div>
          </section>
        )}
        <section>
          <h2>{dayTitle}</h2>
          <pre className="markdown-preview">{content}</pre>
        </section>
      </main>
    </div>
  );
}
