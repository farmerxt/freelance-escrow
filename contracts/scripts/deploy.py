"""
deploy.py — Deploy FreelanceEscrow to GenLayer Testnet (Bradbury)
 
Usage:
  python scripts/deploy.py
 
Requirements:
  pip install genlayer
  export GENLAYER_PRIVATE_KEY=0x...
  export GENLAYER_RPC=https://testnet.genlayer.com  (or studio localhost)
"""
 
import asyncio
import os
from genlayer import GenLayerClient, Account
 
# ── Config ────────────────────────────────────────────────────────────────────
PRIVATE_KEY = os.environ.get("GENLAYER_PRIVATE_KEY")
RPC_URL = os.environ.get("GENLAYER_RPC", "http://localhost:4000/api")
CONTRACT_PATH = "contracts/FreelanceEscrow.py"
 
# ── Example job params (edit before deploying) ────────────────────────────────
FREELANCER_ADDRESS = "0xYOUR_FREELANCER_ADDRESS_HERE"
JOB_BRIEF = """
Design and deliver a responsive landing page for a SaaS product.
 
Requirements:
- Hero section with headline, subheadline, and CTA button
- Feature grid (3 features, icon + title + description each)
- Pricing section (3 tiers: Free, Pro, Enterprise)
- Mobile-first layout, works on 320px–1440px
- Delivered as a single self-contained HTML file with inline CSS
 
Acceptance criteria: matches the Figma mockup shared in the project brief URL.
""".strip()
 
PAYMENT_WEI = 50_000_000_000_000_000  # 0.05 GEN
 
 
async def main():
    assert PRIVATE_KEY, "Set GENLAYER_PRIVATE_KEY env var"
    assert FREELANCER_ADDRESS != "0xYOUR_FREELANCER_ADDRESS_HERE", \
        "Set a real freelancer address"
 
    client = GenLayerClient(endpoint=RPC_URL)
    account = Account.from_key(PRIVATE_KEY)
    client.set_default_account(account)
 
    print(f"Deployer : {account.address}")
    print(f"Freelancer: {FREELANCER_ADDRESS}")
    print(f"Payment  : {PAYMENT_WEI / 1e18:.4f} GEN")
    print(f"RPC      : {RPC_URL}")
    print()
 
    with open(CONTRACT_PATH, "r") as f:
        contract_code = f.read()
 
    print("Deploying FreelanceEscrow...")
    tx_hash = await client.deploy_intelligent_contract(
        code=contract_code,
        args=[FREELANCER_ADDRESS, JOB_BRIEF],
        value=PAYMENT_WEI,
    )
 
    print(f"Deploy tx : {tx_hash}")
    print("Waiting for finalization...")
 
    receipt = await client.wait_for_transaction_receipt(
        tx_hash, status="FINALIZED"
    )
 
    contract_address = receipt["contract_address"]
    print(f"\n✅ Deployed at: {contract_address}")
    print(f"\nSave this address — you'll need it to interact with the contract.")
 
 
if __name__ == "__main__":
    asyncio.run(main())
