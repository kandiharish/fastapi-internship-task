from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(title="Gym Management System")

# -------------------- DATA --------------------
plans = [
    {"id": 1, "name": "Basic", "duration_months": 3, "price": 3000, "includes_classes": False, "includes_trainer": False},
    {"id": 2, "name": "Standard", "duration_months": 6, "price": 5000, "includes_classes": True, "includes_trainer": False},
    {"id": 3, "name": "Premium", "duration_months": 12, "price": 9000, "includes_classes": True, "includes_trainer": True},
    {"id": 4, "name": "Elite", "duration_months": 12, "price": 12000, "includes_classes": True, "includes_trainer": True},
    {"id": 5, "name": "Student", "duration_months": 6, "price": 4000, "includes_classes": False, "includes_trainer": False},
]

memberships = []
membership_counter = 1

class_bookings = []
class_counter = 1

# -------------------- HELPERS --------------------
def find_plan(plan_id):
    for p in plans:
        if p["id"] == plan_id:
            return p
    return None

def calculate_membership_fee(base_price, duration, payment_mode, referral_code=""):
    total = base_price
    discount = 0

    if duration >= 12:
        discount += 20
    elif duration >= 6:
        discount += 10

    if referral_code:
        discount += 5

    total = total * (1 - discount / 100)

    if payment_mode == "emi":
        total += 200

    return total, discount

def filter_plans_logic(max_price, max_duration, includes_classes, includes_trainer):
    result = []
    for p in plans:
        if max_price is not None and p["price"] > max_price:
            continue
        if max_duration is not None and p["duration_months"] > max_duration:
            continue
        if includes_classes is not None and p["includes_classes"] != includes_classes:
            continue
        if includes_trainer is not None and p["includes_trainer"] != includes_trainer:
            continue
        result.append(p)
    return result


@app.get("/")
def home():
    return {"message": "Welcome to IronFit Gym"}

@app.get("/plans")
def get_plans():
    prices = [p["price"] for p in plans]
    return {
        "plans": plans,
        "total": len(plans),
        "min_price": min(prices),
        "max_price": max(prices)
    }

@app.get("/plans/summary")
def plans_summary():
    cheapest = min(plans, key=lambda x: x["price"])
    expensive = max(plans, key=lambda x: x["price"])
    return {
        "total": len(plans),
        "with_classes": len([p for p in plans if p["includes_classes"]]),
        "with_trainer": len([p for p in plans if p["includes_trainer"]]),
        "cheapest": cheapest,
        "most_expensive": expensive
    }


@app.get("/memberships")
def get_memberships():
    return {"memberships": memberships, "total": len(memberships)}


class EnrollRequest(BaseModel):
    member_name: str = Field(min_length=2)
    plan_id: int = Field(gt=0)
    phone: str = Field(min_length=10)
    start_month: str = Field(min_length=3)
    payment_mode: str = "cash"
    referral_code: str = ""


@app.get("/plans/filter")
def filter_plans(
    max_price: Optional[int] = None,
    max_duration: Optional[int] = None,
    includes_classes: Optional[bool] = None,
    includes_trainer: Optional[bool] = None
):
    result = filter_plans_logic(max_price, max_duration, includes_classes, includes_trainer)
    return {"plans": result, "count": len(result)}

# -------------------- POST MEMBERSHIP --------------------
@app.post("/memberships")
def create_membership(req: EnrollRequest):
    global membership_counter

    plan = find_plan(req.plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    total, discount = calculate_membership_fee(
        plan["price"], plan["duration_months"], req.payment_mode, req.referral_code
    )

    membership = {
        "membership_id": membership_counter,
        "member_name": req.member_name,
        "plan_name": plan["name"],
        "duration": plan["duration_months"],
        "total_fee": total,
        "discount_percent": discount,
        "monthly_cost": round(total / plan["duration_months"], 2),
        "status": "active"
    }

    memberships.append(membership)
    membership_counter += 1

    return membership

class NewPlan(BaseModel):
    name: str = Field(min_length=2)
    duration_months: int = Field(gt=0)
    price: int = Field(gt=0)
    includes_classes: bool = False
    includes_trainer: bool = False

@app.post("/plans")
def add_plan(plan: NewPlan, response: Response):
    for p in plans:
        if p["name"].lower() == plan.name.lower():
            raise HTTPException(400, "Duplicate plan")

    new = plan.dict()
    new["id"] = len(plans) + 1
    plans.append(new)
    response.status_code = 201
    return new

@app.put("/plans/{plan_id}")
def update_plan(
    plan_id: int,
    price: Optional[int] = None,
    includes_classes: Optional[bool] = None,
    includes_trainer: Optional[bool] = None
):
    plan = find_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    if price is not None:
        plan["price"] = price
    if includes_classes is not None:
        plan["includes_classes"] = includes_classes
    if includes_trainer is not None:
        plan["includes_trainer"] = includes_trainer

    return plan

@app.delete("/plans/{plan_id}")
def delete_plan(plan_id: int):
    plan = find_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")

    for m in memberships:
        if m["plan_name"] == plan["name"]:
            raise HTTPException(400, "Plan has active members")

    plans.remove(plan)
    return {"message": "Deleted"}
 

@app.post("/classes/book")
def book_class(member_name: str, class_name: str, class_date: str):
    global class_counter

    member = next((m for m in memberships if m["member_name"] == member_name and m["status"] == "active"), None)
    if not member:
        raise HTTPException(400, "No active membership")

    booking = {
        "booking_id": class_counter,
        "member_name": member_name,
        "class_name": class_name,
        "class_date": class_date
    }

    class_bookings.append(booking)
    class_counter += 1

    return booking

@app.get("/classes/bookings")
def get_bookings():
    return class_bookings

@app.delete("/classes/cancel/{booking_id}")
def cancel_booking(booking_id: int):
    for b in class_bookings:
        if b["booking_id"] == booking_id:
            class_bookings.remove(b)
            return {"message": "Cancelled"}
    raise HTTPException(404, "Booking not found")

@app.put("/memberships/{membership_id}/freeze")
def freeze(membership_id: int):
    for m in memberships:
        if m["membership_id"] == membership_id:
            m["status"] = "frozen"
            return m
    raise HTTPException(404, "Not found")

@app.put("/memberships/{membership_id}/reactivate")
def reactivate(membership_id: int):
    for m in memberships:
        if m["membership_id"] == membership_id:
            m["status"] = "active"
            return m
    raise HTTPException(404, "Not found")


@app.get("/plans/search")
def search_plans(keyword: str):
    keyword = keyword.lower()
    result = []
    for p in plans:
        if keyword in p["name"].lower():
            result.append(p)
        elif keyword == "classes" and p["includes_classes"]:
            result.append(p)
        elif keyword == "trainer" and p["includes_trainer"]:
            result.append(p)
    return {"results": result, "total_found": len(result)}

@app.get("/plans/sort")
def sort_plans(sort_by: str = "price", order: str = "asc"):
    if sort_by not in ["price", "name", "duration_months"]:
        raise HTTPException(400, "Invalid sort field")

    reverse = order == "desc"
    return sorted(plans, key=lambda x: x[sort_by], reverse=reverse)

@app.get("/plans/page")
def paginate(page: int = 1, limit: int = 2):
    start = (page - 1) * limit
    data = plans[start:start + limit]
    total_pages = (len(plans) + limit - 1) // limit
    return {"page": page, "total_pages": total_pages, "data": data}

@app.get("/memberships/search")
def search_members(member_name: str):
    result = [m for m in memberships if member_name.lower() in m["member_name"].lower()]
    return result

@app.get("/memberships/sort")
def sort_members(sort_by: str = "total_fee"):
    return sorted(memberships, key=lambda x: x[sort_by])

@app.get("/memberships/page")
def page_members(page: int = 1, limit: int = 2):
    start = (page - 1) * limit
    return memberships[start:start + limit]

@app.get("/plans/browse")
def browse(
    keyword: Optional[str] = None,
    includes_classes: Optional[bool] = None,
    includes_trainer: Optional[bool] = None,
    sort_by: str = "price",
    order: str = "asc",
    page: int = 1,
    limit: int = 2
):
    result = plans

    if keyword:
        result = [p for p in result if keyword.lower() in p["name"].lower()]

    if includes_classes is not None:
        result = [p for p in result if p["includes_classes"] == includes_classes]

    if includes_trainer is not None:
        result = [p for p in result if p["includes_trainer"] == includes_trainer]

    reverse = order == "desc"
    result = sorted(result, key=lambda x: x[sort_by], reverse=reverse)

    start = (page - 1) * limit
    return {
        "data": result[start:start + limit],
        "total": len(result)
    }

@app.get("/plans/{plan_id}")
def get_plan(plan_id: int):
    plan = find_plan(plan_id)
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan 
