import { useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";
import { postStageAction } from "../api/generated";
import type { Me } from "../api/types";
import { hasCapability } from "../api/types";

export function StageActions({
  me,
  openProcess,
  onError,
  onGaps,
}: {
  me: Me;
  openProcess: { id: string; phase?: string; outcome?: string; row_version: number } | undefined;
  onError: (message: string) => void;
  onGaps: (gaps: { kind: string; label: string }[]) => void;
}) {
  const client = useQueryClient();
  if (!openProcess) return null;
  async function act(action: string, rationale: string) {
    if (!openProcess) return;
    onError("");
    onGaps([]);
    try {
      await postStageAction(openProcess.id, {
        action,
        rationale,
        expected_case_version: openProcess.row_version,
      });
      await client.invalidateQueries();
    } catch (caught) {
      if (caught instanceof ApiError) {
        onError(caught.message);
        const missing = caught.details.missing_requirements;
        onGaps(Array.isArray(missing) ? (missing as { kind: string; label: string }[]) : []);
      }
    }
  }
  return (
    <div className="row-actions">
      {openProcess.phase === "due_diligence" && hasCapability(me, "case.submit_ic") && (
        <button className="button" type="button" onClick={() => void act("submit_ic", "Submit the current diligence case to investment committee.")}>
          Submit to IC
        </button>
      )}
      {openProcess.phase === "sourcing" && hasCapability(me, "ic.decide") && (
        <button className="button" type="button" onClick={() => void act("accept_first_look", "Partner accepts a first look on the sourced profile.")}>
          Accept into screening
        </button>
      )}
      {openProcess.phase === "screening" && openProcess.outcome !== "passed" && hasCapability(me, "ic.decide") && (
        <button className="button" type="button" onClick={() => void act("advance_partner_review", "Move the screened company into partner review.")}>
          Move to partner review
        </button>
      )}
      {openProcess.phase === "partner_review" && hasCapability(me, "case.submit_ic") && (
        <button className="button" type="button" onClick={() => void act("open_diligence", "Open diligence from partner review.")}>
          Open diligence
        </button>
      )}
      {openProcess.outcome === "open" && hasCapability(me, "ic.decide") && (
        <button className="button secondary" type="button" onClick={() => void act("pass", "Pass this process on the evidence in hand.")}>
          Pass
        </button>
      )}
      {openProcess.phase === "term_sheet" && hasCapability(me, "ic.decide") && (
        <button className="button" type="button" onClick={() => void act("advance_closing", "Open negotiation and closing from the approved term sheet.")}>
          Open closing
        </button>
      )}
      {openProcess.phase === "negotiation_closing" && openProcess.outcome !== "portfolio" && hasCapability(me, "ic.decide") && (
        <button className="button" type="button" onClick={() => void act("confirm_close", "Confirm the close. This is the step that creates the portfolio record.")}>
          Confirm close
        </button>
      )}
    </div>
  );
}
