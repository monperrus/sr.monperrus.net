#!/bin/bash

source bin/activate

PINECONE_API_KEY=pcsk_HKdSM_NpiuCcJozUNvkmsUjquuSAfdVuob4HmnvkycTBNUSjVX6KK7xaWRVcTu3yK4fJ OPENAI_API_KEY=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   gunicorn --bind 0.0.0.0:8000 app:app
