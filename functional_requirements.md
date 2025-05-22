
[MODE: PLAN]

FUNCTIONAL REQUIREMENTS – Diet-Bot MVP  
======================================

1  WhatsApp Integration  
1.1  The system SHALL expose an HTTPS webhook compatible with Meta’s WhatsApp Business Cloud API, hosted on Google Cloud Run.  
1.2  The webhook SHALL accept and correctly parse inbound events for text messages and image messages.  
1.3  The system SHALL verify the `X-Hub-Signature-256` header on every incoming webhook request.  
1.4  The system SHALL send outbound WhatsApp messages (text, image, or template) using the Meta Cloud API and the authorised business phone number.  
1.5  The system SHALL respond to Meta’s challenge request during webhook setup.

2  User & Profile Management  
2.1  The MVP SHALL support a single pre-configured user document stored in Firebase Realtime Database under `/users/{user_id}/profile`.  
2.2  The profile SHALL contain at minimum:  

• `phone_number` • `name` • `age` • `height_cm` • `weight_kg` • `goal_weight_kg` • `activity_level` • `timezone` (default `Europe/London`) • `schedule` object with `morning_checkin` and `daily_recap` (defaults 07:00 and 21:00).  
2.3  The system SHALL calculate and persist a daily calorie budget for the user based on profile data (e.g., Mifflin-St Jeor with activity multiplier minus deficit).

3  Message Logging  
3.1  Every inbound user message and outbound AI reply SHALL be stored as a distinct record at `/users/{user_id}/messages/{message_id}`.  
3.2  Each message record SHALL conform to this Pydantic schema:  

• `id` • `user_id` • `timestamp` (ISO-8601) • `role` ("user" | "ai") • `type` ("text" | "image") • `content`  
• `gcs_path` (optional)  
• `image_data` (optional, required when `type == "image"`) containing { `width`, `height`, `mime_type`, `resolution` }.  
• `food` (List\[Food\]) – may be empty.  
• `llm_parameters` (optional, only when `role == "ai"`).  

3.3  `food` objects SHALL contain:  

• `name` • `estimated_grams` • `calories` • `macros` { `protein_g`, `carbs_g`, `fat_g` }.  

3.4  `llm_parameters` SHALL include:  

`model`, `temperature`, `top_p`, `max_tokens`, `prompt_tokens`, `completion_tokens`, `total_tokens`.

4  Image Handling & Storage  
4.1  If an inbound message contains an image, the system SHALL download the image via the WhatsApp media API.  
4.2  The image SHALL be stored in a Google Cloud Storage bucket **`dietbot-images`** under a path containing the `user_id` and `message_id`.  
4.3  The image SHALL be validated and resized as necessary to satisfy OpenAI vision limits.  
4.4  A signed URL (or public URL per bucket policy) SHALL be saved in `gcs_path` and used for downstream processing.

5  Calorie & Macro Estimation  
5.1  The system SHALL call OpenAI GPT-4o Vision to analyse food images and return structured JSON describing foods, quantities, calories, and macros.  
5.2  If the GPT call fails, a heuristic calorie estimator SHALL provide fallback values.  
5.3  The resulting Food list SHALL be written into the `food` field of the corresponding message record.

6  LangChain-Based AI Agent  
6.1  The system SHALL instantiate a LangChain Structured Chat Agent with an OpenAI model whose **name is supplied via environment variable `OPENAI_MODEL`** (default `gpt-4o`).  
6.2  The agent SHALL run with contextual awareness of the invoking `user_id`, enabling retrieval of that user’s profile and recent messages.  
6.3  The agent SHALL operate under a single system prompt positioning it as a supportive diet coach.  
6.4  On every invocation, the agent SHALL select exactly one of the following tools and output **only** the tool’s JSON schema (no free-text outside JSON):  

• `store_message` • `fetch_recent_messages` • `estimate_calories` • `compute_daily_budget` • `generate_daily_report` • `respond` { `response`: str } • `end_conversation`  

6.5  All tool input and output schemas SHALL be implemented as Pydantic models.  
6.6  After the agent produces a tool call, the orchestrator SHALL execute the tool, persist any AI response as a new message record, and, when appropriate, send a WhatsApp reply.

7  Scheduling & Automated Messages  
7.1  Two Google Cloud Scheduler jobs SHALL invoke HTTPS endpoints on Cloud Run:  

• `/scheduled/morning_checkin` at the user’s `schedule.morning_checkin` time.  
• `/scheduled/daily_recap` at the user’s `schedule.daily_recap` time.  

7.2  Each job request SHALL include a custom header `Scheduler-Token` validated by the service.  
7.3  Morning check-in messages SHALL remind the user of their daily calorie budget and provide motivational support.  
7.4  Daily recap generation SHALL aggregate the day’s messages, compute totals, render a PNG summary, store it in GCS, and send it via WhatsApp.

8  Daily Report Generation  
8.1  The report generator SHALL fetch all messages for the current day, sum calories/macros, and calculate remaining budget.  
8.2  A single PNG SHALL be produced containing key metrics and a simple chart.  
8.3  The PNG SHALL be uploaded to `dietbot-images`, and the resulting link SHALL be sent in a WhatsApp media message.

9  Security & Access Control  
9.1  Firebase Realtime Database rules SHALL deny all unauthenticated access; only the Cloud Run service account SHALL have read/write permissions.  
9.2  The Cloud Run service account SHALL possess Storage Object Admin rights for the `dietbot-images` bucket.  
9.3  OpenAI and WhatsApp API keys SHALL be provided via environment variables; `.env.example` SHALL list placeholders.  
9.4  All outbound HTTP requests SHALL use HTTPS.

10  Observability & Error Handling  
10.1  The system SHALL emit structured JSON logs at INFO level for normal ops and ERROR for failures.  
10.2  Failed external-API calls SHALL be retried with exponential back-off up to three attempts.  
10.3  Unhandled exceptions SHALL return HTTP 500 with minimal external detail while logging full stack traces.  
10.4  A `/healthz` endpoint SHALL return HTTP 200 for readiness probes.

11  Configuration & Deployment  
11.1  A Dockerfile SHALL containerise the FastAPI app on Python 3.11-slim and expose port 8080.  
11.2  All configuration values (env vars, scheduler token, bucket name, OpenAI model) SHALL be supplied at deploy time.  
11.3  A README SHALL document local development (`uvicorn --reload`) and ngrok tunnelling for WhatsApp webhook validation.  
11.4  A standalone script `scripts/create_user.py` SHALL be provided to create/update the pre-configured user profile in Firebase; **the script SHALL NOT execute automatically**.

----------------------------------------------------
IMPLEMENTATION CHECKLIST  
----------------------------------------------------
1. Scaffold repository structure (`app/`, `services/`, `handlers/`, `utils/`, `reports/`, `infra/`, `scripts/`).  
2. Add `requirements.txt` with FastAPI, uvicorn, python-dotenv, openai, google-cloud-{realtime-db,storage}, httpx, Pillow, langchain, pydantic.  
3. Implement `app/config.py` to load env vars, including `OPENAI_MODEL` and bucket `dietbot-images`.  
4. Create Pydantic models: UserProfile, Message, Food, ImageData, LLMParameters, and all LangChain tool schemas.  
5. Build Firebase Realtime DB helper for CRUD at `/users/{user_id}/messages/{message_id}` and `/profile`.  
6. Build Cloud Storage helper targeting `dietbot-images`.  
7. Write WhatsApp API wrapper for send/receive (text, image, template).  
8. Implement OpenAI wrapper that takes `OPENAI_MODEL` from env and supports both chat and vision calls.  
9. Add heuristic calorie estimator fallback in `utils/calorie_estimator.py`.  
10. Implement LangChain tools and Structured Chat Agent enforcing JSON-only outputs.  
11. Implement webhook handler: parse incoming event → run agent → execute tool → store message → send reply.  
12. Build `/scheduled/morning_checkin` and `/scheduled/daily_recap` handlers with Scheduler-Token validation.  
13. Implement PNG report generator in `reports/report_generator.py`.  
14. Configure Dockerfile, Cloud Run deployment YAML, and Cloud Scheduler job definitions.  
15. Write Firebase security rules denying public access and allowing Cloud Run service-account access.  
16. Add `.env.example` with placeholders for all required env vars.  
17. Provide `scripts/create_user.py` to populate the initial user profile.  
18. Deploy Cloud Run service, set env vars, and grant IAM roles.  
19. Create Cloud Scheduler jobs pointing to the Cloud Run endpoints with proper headers.  
20. Point Meta WhatsApp webhook to the Cloud Run URL and complete verification.  
21. End-to-end testing: text logging, image logging, morning check-in, daily recap PNG delivery.
