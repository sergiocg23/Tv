#!/bin/sh
if ! curl -fs -k https://127.0.0.1/healthz | grep -q '^OK$'; then
  exit 1
fi