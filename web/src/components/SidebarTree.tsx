import type { JournalTree } from "../api";

type Props = {
  tree: JournalTree;
  selectedDay: string | null;
  onSelectDay: (day: string) => void;
};

export function SidebarTree({ tree, selectedDay, onSelectDay }: Props) {
  return (
    <aside className="sidebar">
      <h2>Dnevi</h2>
      {tree.length === 0 && <p className="muted">Ni vnosov.</p>}
      {tree.map((yearNode) => (
        <details key={yearNode.year} open>
          <summary>{yearNode.year}</summary>
          {yearNode.months.map((monthNode) => (
            <details key={`${yearNode.year}-${monthNode.month}`} open>
              <summary>{monthNode.month}</summary>
              <ul>
                {monthNode.days.map((day) => (
                  <li key={day}>
                    <button
                      className={selectedDay === day ? "day-button active" : "day-button"}
                      onClick={() => onSelectDay(day)}
                    >
                      {day}
                    </button>
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </details>
      ))}
    </aside>
  );
}
