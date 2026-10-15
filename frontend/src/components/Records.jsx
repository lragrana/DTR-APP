const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "—");

export default function Records({ records, showUser = false, onDelete }) {
  if (!records.length) return <p>No records yet.</p>;
  return (
    <table>
      <thead>
        <tr>
          {showUser && <th>User</th>}
          <th>Check in</th>
          <th>Check out</th>
          <th>Notes</th>
          {onDelete && <th />}
        </tr>
      </thead>
      <tbody>
        {records.map((r) => (
          <tr key={r.id}>
            {showUser && <td>{r.username}</td>}
            <td>{fmt(r.check_in)}</td>
            <td>{fmt(r.check_out)}</td>
            <td>{r.notes || ""}</td>
            {onDelete && <td><button className="danger" onClick={() => onDelete(r)}>Delete</button></td>}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
