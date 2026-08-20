import random
from typing import Dict, Any
from src.classifier.models import RootCauseCategory
from src.policy.models import ActionType, Action


class EconomicSimulator:
    """
    Unified, transparent economic simulator for evaluating payment revenue recovery.
    Calculates Gross Recovered Revenue, Risk & Operational Penalties, and Net Recovered Revenue.

    SIMULATION ASSUMPTIONS (Explicitly documented simulation model, NOT actual Razorpay statistics):

    1. Recovery Probabilities by Ground-Truth Cause & Action:
       - BANK_TRANSIENT:
         - RETRY_SCHEDULED (with backoff delay): 85% recovery rate
         - RETRY_NOW (immediate retry during active outage): 10% recovery rate
       - INSUFFICIENT_FUNDS:
         - RETRY_SCHEDULED (with 24h cooldown): 60% recovery rate
         - RETRY_NOW (immediate retry before payday): 10% recovery rate
       - CUSTOMER_ABANDONMENT / SESSION_EXPIRED:
         - NUDGE_CUSTOMER (Customer Recovery Payment Link): 50% recovery rate
         - RETRY_NOW / RETRY_SCHEDULED (automated retry without customer nudge): 15% recovery rate
       - RISK_BLOCK:
         - RETRY_NOW / RETRY_SCHEDULED: 0% recovery rate (100% failure rate)
         - ESCALATE_HUMAN: 0% automated recovery, ₹0 penalty (prevents chargeback loss)
       - UNKNOWN:
         - NUDGE_CUSTOMER: 30% recovery rate
         - RETRY_SCHEDULED: 20% recovery rate

    2. Risk & Operational Penalties (Applied uniformly to ALL systems based solely on Action & Ground Truth):
       - False-Retry Penalty: ₹500 per auto-retry attempt on RISK_BLOCK transactions.
       - High-Value Dispute / Chargeback Exposure Penalty: ₹1,000 fixed risk penalty per automated
         retry on high-value transactions (amount >= ₹5,000 / 500,000 paise) when executed without
         human review on high-risk/unvetted causes (RISK_BLOCK, CUSTOMER_ABANDONMENT, SESSION_EXPIRED, UNKNOWN).
       - Retry Spam Penalty: ₹200 gateway/network penalty per automated retry attempt when
         repeat attempt count >= 3 (excessive retry spam).
       - Unnecessary Escalation Labor Cost: ₹150 labor cost per human escalation on straightforward
         recoverable errors (BANK_TRANSIENT, INSUFFICIENT_FUNDS).
    """

    def __init__(
        self,
        false_retry_penalty_inr: float = 500.0,
        high_value_dispute_penalty_inr: float = 1000.0,
        retry_spam_penalty_inr: float = 200.0,
        unnecessary_escalation_cost_inr: float = 150.0,
        high_value_threshold_paise: int = 500000,  # ₹5,000
    ):
        self.false_retry_penalty_inr = false_retry_penalty_inr
        self.high_value_dispute_penalty_inr = high_value_dispute_penalty_inr
        self.retry_spam_penalty_inr = retry_spam_penalty_inr
        self.unnecessary_escalation_cost_inr = unnecessary_escalation_cost_inr
        self.high_value_threshold_paise = high_value_threshold_paise

    def simulate_event_outcome(
        self,
        event: Dict[str, Any],
        ground_truth: RootCauseCategory,
        action: Action,
        seed: int = 42,
    ) -> Dict[str, Any]:
        amount_paise = event["amount"]
        amount_inr = amount_paise / 100.0
        action_type = action.type
        attempt_number = event.get("attempt_number", 1)

        attempted = action_type in (
            ActionType.RETRY_NOW,
            ActionType.RETRY_SCHEDULED,
            ActionType.NUDGE_CUSTOMER,
        )
        successful = False
        gross_recovered = 0.0
        penalties = 0.0
        penalty_reasons = []
        is_unsafe_action = False

        # Deterministic pseudo-random seed per event order_id for reproducible outcome simulation
        rng = random.Random(f"{event['order_id']}_{action_type.value}_{seed}")
        roll = rng.random()

        if action_type in (ActionType.RETRY_NOW, ActionType.RETRY_SCHEDULED):
            # Check Excessive Retry Spam Penalty (attempt >= 3)
            if attempt_number >= 3:
                penalties += self.retry_spam_penalty_inr
                penalty_reasons.append(f"Excessive retry spam penalty (attempt #{attempt_number}): -₹{self.retry_spam_penalty_inr:.2f}")

            if ground_truth == RootCauseCategory.BANK_TRANSIENT:
                prob = 0.85 if action_type == ActionType.RETRY_SCHEDULED else 0.10
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr

            elif ground_truth == RootCauseCategory.INSUFFICIENT_FUNDS:
                prob = 0.60 if action_type == ActionType.RETRY_SCHEDULED else 0.10
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr

            elif ground_truth in (RootCauseCategory.CUSTOMER_ABANDONMENT, RootCauseCategory.SESSION_EXPIRED):
                prob = 0.15
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr
                # High-value automated retry on abandonment/expired session carries dispute risk
                if amount_paise >= self.high_value_threshold_paise:
                    is_unsafe_action = True
                    penalties += self.high_value_dispute_penalty_inr
                    penalty_reasons.append(f"Un-reviewed high-value auto-retry dispute penalty (₹{amount_inr:,.2f}): -₹{self.high_value_dispute_penalty_inr:.2f}")

            elif ground_truth == RootCauseCategory.RISK_BLOCK:
                # 0% success, mandatory false-retry penalty for attempting auto-retry on fraud/risk block
                successful = False
                is_unsafe_action = True
                penalties += self.false_retry_penalty_inr
                penalty_reasons.append(f"False retry on RISK_BLOCK: -₹{self.false_retry_penalty_inr:.2f}")
                if amount_paise >= self.high_value_threshold_paise:
                    penalties += self.high_value_dispute_penalty_inr
                    penalty_reasons.append(f"High-value fraud retry chargeback penalty (₹{amount_inr:,.2f}): -₹{self.high_value_dispute_penalty_inr:.2f}")

            elif ground_truth == RootCauseCategory.UNKNOWN:
                prob = 0.20
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr
                if amount_paise >= self.high_value_threshold_paise:
                    is_unsafe_action = True
                    penalties += self.high_value_dispute_penalty_inr
                    penalty_reasons.append(f"Un-reviewed high-value unknown retry dispute penalty (₹{amount_inr:,.2f}): -₹{self.high_value_dispute_penalty_inr:.2f}")

        elif action_type == ActionType.NUDGE_CUSTOMER:
            if ground_truth in (RootCauseCategory.CUSTOMER_ABANDONMENT, RootCauseCategory.SESSION_EXPIRED):
                prob = 0.50
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr
            elif ground_truth == RootCauseCategory.UNKNOWN:
                prob = 0.30
                if roll < prob:
                    successful = True
                    gross_recovered = amount_inr

        elif action_type == ActionType.ESCALATE_HUMAN:
            # Human escalation: 0% immediate automated recovery.
            # If unnecessary escalation on simple BANK_TRANSIENT or INSUFFICIENT_FUNDS -> labor cost penalty
            if ground_truth in (RootCauseCategory.BANK_TRANSIENT, RootCauseCategory.INSUFFICIENT_FUNDS):
                penalties += self.unnecessary_escalation_cost_inr
                penalty_reasons.append(f"Unnecessary human escalation labor cost: -₹{self.unnecessary_escalation_cost_inr:.2f}")

        net_recovered = gross_recovered - penalties

        return {
            "order_id": event["order_id"],
            "amount_inr": amount_inr,
            "action_type": action_type.value,
            "attempted": attempted,
            "successful": successful,
            "is_unsafe_action": is_unsafe_action,
            "gross_recovered_inr": round(gross_recovered, 2),
            "penalties_inr": round(penalties, 2),
            "net_recovered_inr": round(net_recovered, 2),
            "penalty_reasons": penalty_reasons,
        }
