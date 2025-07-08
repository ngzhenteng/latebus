A Telegram Bot to obtain bus arrival timings

Utilizes apis from:
https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf

Feature ideas:
- Timed Alerts for Bus Stop + Bus Number: /settimer {bus_stop_code} {bus_number} + {cron}: bot obtains chat_id + user_id, and schedules a timed message using job_queue = application.job_queue
