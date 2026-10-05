from faststream.rabbit import ExchangeType, RabbitExchange, RabbitQueue

PAYMENTS_EXCHANGE = RabbitExchange("payments", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_NEW_QUEUE = RabbitQueue("payments.new", routing_key="payments.new", durable=True)
PAYMENTS_NEW_ROUTING_KEY = "payments.new"

PAYMENTS_RETRY_EXCHANGE = RabbitExchange("payments.retry", type=ExchangeType.DIRECT, durable=True)

_RETRY_TTLS = {1: 2000, 2: 4000, 3: 8000}
PAYMENTS_RETRY_QUEUES = [
    RabbitQueue(
        f"payments.retry.{n}",
        routing_key=f"payments.retry.{n}",
        durable=True,
        arguments={
            "x-message-ttl": ttl,
            "x-dead-letter-exchange": "payments",
            "x-dead-letter-routing-key": "payments.new",
        },
    )
    for n, ttl in _RETRY_TTLS.items()
]

PAYMENTS_DLX = RabbitExchange("payments.dlx", type=ExchangeType.DIRECT, durable=True)
PAYMENTS_DLQ = RabbitQueue("payments.dlq", routing_key="payments.dlq", durable=True)
PAYMENTS_DLQ_ROUTING_KEY = "payments.dlq"


async def declare_topology(broker) -> None:
    payments = await broker.declare_exchange(PAYMENTS_EXCHANGE)
    new_q = await broker.declare_queue(PAYMENTS_NEW_QUEUE)
    await new_q.bind(payments, routing_key=PAYMENTS_NEW_ROUTING_KEY)

    retry_ex = await broker.declare_exchange(PAYMENTS_RETRY_EXCHANGE)
    for rq in PAYMENTS_RETRY_QUEUES:
        q = await broker.declare_queue(rq)
        await q.bind(retry_ex, routing_key=rq.routing_key)

    dlx = await broker.declare_exchange(PAYMENTS_DLX)
    dlq = await broker.declare_queue(PAYMENTS_DLQ)
    await dlq.bind(dlx, routing_key=PAYMENTS_DLQ_ROUTING_KEY)