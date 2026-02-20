import { useState } from "react";

type Props = {
  onPropose: (text: string, instruction?: string) => Promise<void>;
  disabled?: boolean;
};

export function WriteComposer({ onPropose, disabled }: Props) {
  const [text, setText] = useState("");
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (!text.trim() || loading || disabled) return;
    setLoading(true);
    try {
      await onPropose(text, instruction || undefined);
      setText("");
      setInstruction("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="composer">
      <h3>Dodaj vnos</h3>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder="Napiši, kaj se je zgodilo ..."
      />
      <input
        value={instruction}
        onChange={(e) => setInstruction(e.target.value)}
        placeholder="Dodatna navodila (neobvezno)"
      />
      <button onClick={submit} disabled={loading || disabled}>
        {loading ? "Predlagam ..." : "Predlagaj spremembo"}
      </button>
    </section>
  );
}
