# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
 
# ---------------------------------------------------------------------------
#  FreelanceEscrow — AI-Powered Freelance Escrow on GenLayer
#
#  Flow:
#    1. Client deploys contract with freelancer address + job brief
#       and attaches GEN payment (held in contract balance).
#    2. Freelancer submits work (description + optional URL).
#    3. Anyone calls evaluate_submission() — GenLayer validators each
#       run the LLM prompt and reach Optimistic Democracy consensus:
#          → approved  : payment auto-released to freelancer
#          → rejected  : client can re-evaluate or override manually
#    4. Client can always manually approve or request a refund (pre-submit).
# ---------------------------------------------------------------------------
 
class FreelanceEscrow(gl.Contract):
    # ── Parties ─────────────────────────────────────────────────────────────
    client: Address
    freelancer: Address
 
    # ── Job details ──────────────────────────────────────────────────────────
    job_brief: str          # Natural-language description of the deliverable
    payment_amount: u256    # Amount locked in escrow (in wei / smallest unit)
 
    # ── Submission ───────────────────────────────────────────────────────────
    submission_text: str    # Freelancer's description of completed work
    submission_url: str     # Optional URL (GitHub, Figma, Loom, etc.)
 
    # ── State machine ────────────────────────────────────────────────────────
    # "open" → "submitted" → "approved" | "rejected"
    # "open" → "refunded"  (client cancels before submission)
    status: str
 
    # ── AI evaluation log ────────────────────────────────────────────────────
    ai_reasoning: str       # Stored for transparency / dispute reference
 
    # =========================================================================
    # Constructor — called at deployment. Attach GEN payment as tx value.
    # =========================================================================
    def __init__(self, freelancer: str, job_brief: str) -> None:
        assert gl.message.value > u256(0), "Must attach payment when creating escrow"
        assert len(job_brief) >= 10, "Job brief is too short"
 
        self.client = gl.message.sender_account
        self.freelancer = Address(freelancer)
        self.job_brief = job_brief
        self.payment_amount = gl.message.value
        self.submission_text = ""
        self.submission_url = ""
        self.status = "open"
        self.ai_reasoning = ""
 
    # =========================================================================
    # Read methods
    # =========================================================================
 
    @gl.public.view
    def get_status(self) -> str:
        return self.status
 
    @gl.public.view
    def get_brief(self) -> str:
        return self.job_brief
 
    @gl.public.view
    def get_payment_amount(self) -> u256:
        return self.payment_amount
 
    @gl.public.view
    def get_parties(self) -> str:
        return json.dumps({
            "client": self.client.as_hex,
            "freelancer": self.freelancer.as_hex,
        })
 
    @gl.public.view
    def get_submission(self) -> str:
        return json.dumps({
            "text": self.submission_text,
            "url": self.submission_url,
            "status": self.status,
        })
 
    @gl.public.view
    def get_ai_reasoning(self) -> str:
        return self.ai_reasoning
 
    # =========================================================================
    # Freelancer: submit completed work
    # =========================================================================
 
    @gl.public.write
    def submit_work(self, submission_text: str, submission_url: str) -> None:
        """
        Freelancer submits proof of work.
        submission_text  — description of what was delivered
        submission_url   — link to deliverable (optional, pass "" if none)
        """
        assert gl.message.sender_account == self.freelancer, \
            "Only the assigned freelancer can submit work"
        assert self.status == "open", \
            f"Cannot submit: contract is '{self.status}'"
        assert len(submission_text) >= 10, \
            "Submission description is too short"
 
        self.submission_text = submission_text
        self.submission_url = submission_url
        self.status = "submitted"
 
    # =========================================================================
    # AI-powered evaluation — Optimistic Democracy consensus
    # =========================================================================
 
    @gl.public.write
    def evaluate_submission(self) -> None:
        """
        Triggers LLM-based evaluation of the submission against the job brief.
        GenLayer validators independently run the prompt and vote on the outcome.
        Consensus is reached via Optimistic Democracy — no human arbitrator needed.
 
        On approval  → payment released to freelancer automatically.
        On rejection → status set to "rejected"; client can override or re-trigger.
        """
        assert self.status == "submitted", \
            f"Nothing to evaluate: status is '{self.status}'"
 
        # Capture into local vars — storage is inaccessible from non-det blocks
        brief = self.job_brief
        sub_text = self.submission_text
        sub_url = self.submission_url
 
        prompt = f"""You are a neutral arbiter evaluating whether a freelancer's deliverable fulfills a client's job brief.
 
══ JOB BRIEF ══
{brief}
 
══ FREELANCER SUBMISSION ══
Description: {sub_text}
URL / Link: {sub_url if sub_url else "(none provided)"}
 
══ YOUR TASK ══
Decide whether this submission adequately fulfills the job brief.
Ask yourself:
  • Does it address all core requirements stated in the brief?
  • Is the scope of work appropriate?
  • Would a reasonable client accept this as a satisfactory completion of the contract?
 
Respond ONLY with valid JSON — no extra text, no markdown:
{{"approved": true, "reasoning": "one or two sentences"}}
or
{{"approved": false, "reasoning": "one or two sentences"}}"""
 
        def leader_fn():
            return gl.nondet.exec_prompt(prompt, response_format="json")
 
        def validator_fn(leaders_res) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            my_result = leader_fn()
            # Consensus: validators agree on the boolean verdict
            return my_result["approved"] == leaders_res.calldata["approved"]
 
        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
 
        # Store AI reasoning on-chain for transparency
        self.ai_reasoning = result.get("reasoning", "")
 
        if result["approved"]:
            self.status = "approved"
            gl.ContractAt(self.freelancer).emit_transfer(value=self.payment_amount)
        else:
            self.status = "rejected"
 
    # =========================================================================
    # Client: manual approval (override AI rejection or skip AI)
    # =========================================================================
 
    @gl.public.write
    def client_approve(self) -> None:
        """
        Client manually approves and releases payment.
        Can be used to override an AI rejection or to skip evaluation entirely.
        """
        assert gl.message.sender_account == self.client, \
            "Only the client can manually approve"
        assert self.status in ("submitted", "rejected"), \
            f"Cannot approve: status is '{self.status}'"
 
        self.status = "approved"
        gl.ContractAt(self.freelancer).emit_transfer(value=self.payment_amount)
 
    # =========================================================================
    # Client: refund (only before freelancer submits)
    # =========================================================================
 
    @gl.public.write
    def refund(self) -> None:
        """
        Client reclaims escrow funds.
        Only allowed while status is 'open' (no submission yet).
        """
        assert gl.message.sender_account == self.client, \
            "Only the client can request a refund"
        assert self.status == "open", \
            "Refund only possible before work is submitted"
 
        self.status = "refunded"
        gl.ContractAt(self.client).emit_transfer(value=self.payment_amount)
 
    # =========================================================================
    # Client: top-up escrow (e.g. revised scope agreed off-chain)
    # =========================================================================
 
    @gl.public.write.payable
    def top_up(self) -> None:
        """
        Add more funds to the escrow (revised scope, bonus, etc.).
        Only allowed while status is 'open'.
        """
        assert gl.message.sender_account == self.client, \
            "Only the client can top up the escrow"
        assert self.status == "open", \
            "Can only top up while contract is open"
        assert gl.message.value > u256(0), \
            "Top-up amount must be greater than zero"
 
        self.payment_amount = self.payment_amount + gl.message.value
