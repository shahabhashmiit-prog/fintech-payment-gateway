from flask import Flask, request, jsonify
import uuid
import random
import logging
import redis
import json

app = Flask(__name__)

# Redis is used only to store idempotent requests
# If Redis is not running, app will fail (expected for demo)
redis_client = redis.Redis(
    host="localhost",   # Use localhost on WSL/Linux
    port=6379,
    decode_responses=True
)

# Basic logging for transaction tracking
logging.basicConfig(
    filename="transactions.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def validate_request(payload):
    if payload is None:
        return False

    if "amount" not in payload:
        return False

    try:
        amount = float(payload["amount"])
        if amount <= 0:
            return False
    except (ValueError, TypeError):
        return False

    return True


@app.route("/")
def index():
    return jsonify({
        "service": "Payment API",
        "message": "Service is running"
    })


@app.route("/pay", methods=["POST"])
def pay():
    # Idempotency key avoids duplicate charges on retries
    idem_key = request.headers.get("Idempotency-Key")

    if not idem_key:
        return jsonify({
            "error": "Idempotency-Key header is required"
        }), 400

    # If request already processed, return cached result
    cached = redis_client.get(f"idemp:{idem_key}")
    if cached:
        return jsonify(json.loads(cached)), 200

    data = request.get_json(silent=True)

    if not validate_request(data):
        logging.warning("Invalid payment request: %s", data)
        return jsonify({
            "error": "Invalid request data"
        }), 400

    amount = float(data["amount"])
    transaction_id = str(uuid.uuid4())

    # Simulate payment processing
    status = random.choice(["SUCCESS", "FAILED"])

    response = {
        "transaction_id": transaction_id,
        "amount": amount,
        "status": status
    }

    # Cache response for idempotency (24 hours)
    redis_client.setex(
        f"idemp:{idem_key}",
        60 * 60 * 24,
        json.dumps(response)
    )

    logging.info(
        "transaction_id=%s amount=%.2f status=%s",
        transaction_id, amount, status
    )

    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
