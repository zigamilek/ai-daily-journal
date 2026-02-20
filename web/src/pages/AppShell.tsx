import { useEffect, useMemo, useState } from "react";
import { api, type JournalTree, type ProposalResponse } from "../api";
import { DiffViewer } from "../components/DiffViewer";
import { SidebarTree } from "../components/SidebarTree";
import { WriteComposer } from "../components/WriteComposer";

type Me = { id: number; email: string; timezone: string };
type ProposalMode = "entry" | "day-edit";

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
  const [proposalMode, setProposalMode] = useState<ProposalMode>("entry");
  const [lastInputText, setLastInputText] = useState("");
  const [revisionInstruction, setRevisionInstruction] = useState("");
  const [dayEditOpen, setDayEditOpen] = useState(false);
  const [dayEditText, setDayEditText] = useState("");
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
    setDayEditOpen(false);
    setDayEditText(file.content);
  }

  async function onPropose(text: string, instruction?: string) {
    try {
      setError(null);
      setLastInputText(text);
      const next = await api.propose(text, proposal?.session_id, instruction);
      setProposal(next);
      setProposalMode("entry");
    } catch (err) {
      setError(String(err));
    }
  }

  async function onProposeDayEdit() {
    if (!selectedDay) return;
    try {
      setError(null);
      const next = await api.proposeDayEdit(
        selectedDay,
        dayEditText,
        proposalMode === "day-edit" ? proposal?.session_id : undefined
      );
      setProposal(next);
      setProposalMode("day-edit");
    } catch (err) {
      setError(String(err));
    }
  }

  async function onConfirm() {
    if (!proposal) return;
    const response = await api.confirm(proposal.session_id, randomKey());
    setProposal(null);
    setProposalMode("entry");
    setSelectedDay(response.day_date);
    setContent(response.final_content);
    setDayEditText(response.final_content);
    setDayEditOpen(false);
    await refresh();
  }

  async function onCancel() {
    if (!proposal) return;
    await api.cancel(proposal.session_id);
    setProposal(null);
    setProposalMode("entry");
    setRevisionInstruction("");
  }

  async function onRevise() {
    if (proposalMode !== "entry") return;
    if (!proposal) return;
    const lastEntry =
      proposal.proposed_entries.length > 0
        ? proposal.proposed_entries[proposal.proposed_entries.length - 1]
        : undefined;
    const baseText = lastInputText || lastEntry?.source_user_text || "";
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
            {proposalMode === "entry" && (
              <input
                value={revisionInstruction}
                onChange={(e) => setRevisionInstruction(e.target.value)}
                placeholder="Navodilo za popravek (npr. bolj jedrnato)"
              />
            )}
            <div className="row">
              <button onClick={() => void onConfirm()}>Potrdi</button>
              {proposalMode === "entry" && (
                <button onClick={() => void onRevise()}>Zahtevaj spremembe</button>
              )}
              <button onClick={() => void onCancel()}>Prekliči</button>
            </div>
          </section>
        )}
        <section>
          <div className="row row-between">
            <h2>{dayTitle}</h2>
            <button
              disabled={!selectedDay}
              onClick={() => {
                setDayEditOpen((prev) => !prev);
                setDayEditText(content);
              }}
            >
              {dayEditOpen ? "Zapri urejanje" : "Uredi dan"}
            </button>
          </div>
          {dayEditOpen && (
            <section className="composer">
              <h3>Uredi vsebino dneva</h3>
              <textarea
                value={dayEditText}
                onChange={(e) => setDayEditText(e.target.value)}
                rows={8}
                placeholder="Uredi vnose dneva ..."
              />
              <button onClick={() => void onProposeDayEdit()}>Predlagaj ureditev dneva</button>
            </section>
          )}
          <pre className="day-preview">{content}</pre>
        </section>
      </main>
    </div>
  );
}
