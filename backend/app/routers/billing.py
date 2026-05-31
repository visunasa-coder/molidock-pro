from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import Plan, User


router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout/{plan}")
def create_checkout(plan: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    price_by_plan = {"pro": settings.stripe_pro_price_id, "lab": settings.stripe_lab_price_id}
    if plan not in price_by_plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Supported plans: pro, lab")
    if not settings.stripe_secret_key or not price_by_plan[plan]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe is not configured")

    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe package is not installed") from exc

    stripe.api_key = settings.stripe_secret_key
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user.email,
        line_items=[{"price": price_by_plan[plan], "quantity": 1}],
        success_url=f"{settings.frontend_base_url}/?billing=success",
        cancel_url=f"{settings.frontend_base_url}/?billing=cancel",
        metadata={"user_id": str(user.id), "plan": plan},
        subscription_data={"metadata": {"user_id": str(user.id), "plan": plan}},
    )
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe webhook is not configured")

    try:
        import stripe
    except ImportError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe package is not installed") from exc

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook") from exc

    if event["type"] in {"checkout.session.completed", "customer.subscription.updated"}:
        data = event["data"]["object"]
        metadata = data.get("metadata") or {}
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")
        if user_id and plan in {Plan.pro.value, Plan.lab.value, Plan.enterprise.value}:
            user = db.get(User, int(user_id))
            if user:
                user.plan = Plan(plan)
                user.stripe_customer_id = data.get("customer") or user.stripe_customer_id
                db.add(user)
                db.commit()

    return {"received": True}

