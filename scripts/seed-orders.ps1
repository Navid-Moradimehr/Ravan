$ErrorActionPreference = "Stop"

docker compose -f docker/docker-compose.yml exec -T postgres psql -U stream -d stream_engine -c "INSERT INTO orders (customer_id, status, amount, currency) VALUES ('customer-' || floor(random() * 1000)::text, 'created', round((random() * 500 + 10)::numeric, 2), 'USD');"
docker compose -f docker/docker-compose.yml exec -T postgres psql -U stream -d stream_engine -c "UPDATE orders SET status = 'paid', updated_at = now() WHERE id = (SELECT max(id) FROM orders);"
