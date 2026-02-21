#!/bin/sh

mkdir -p /app/instance
python "db maker.py" || true

if [ "${SEED_ON_START:-false}" = "true" ]
then
  if [ ! -f /app/instance/.seeded ]
  then
    python seeding.py || true
    touch /app/instance/.seeded || true
  fi
fi

exec gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 app:app
