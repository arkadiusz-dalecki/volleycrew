export function LoadingCard({ message }: { message: string }) {
  return (
    <section className="card loading-card" role="status">
      <p>{message}</p>
      <div className="loading-placeholder" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
    </section>
  );
}
