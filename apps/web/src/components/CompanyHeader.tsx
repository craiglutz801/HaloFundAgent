export function CompanyHeader({
  name,
  legalName,
  stage,
  owner,
}: {
  name: string;
  legalName: string;
  stage: string;
  owner: string;
}) {
  return (
    <header className="page-head">
      <div>
        <p className="kicker">{legalName}</p>
        <h1>{name}</h1>
        <p>Owner {owner}</p>
      </div>
      <span className="badge">{stage.replaceAll("_", " ")}</span>
    </header>
  );
}
