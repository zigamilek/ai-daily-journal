type Props = {
  diffText: string;
};

export function DiffViewer({ diffText }: Props) {
  return (
    <section>
      <h3>Predlagana razlika</h3>
      <pre className="diff-viewer">{diffText}</pre>
    </section>
  );
}
