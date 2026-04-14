Мини-дашборд для синхронизации заказов из RetailCRM в Supabase с аналитикой и уведомлениями в Telegram.

Ссылки
Dashboard (Vercel): [твоя ссылка на версель]

GitHub Repo: [ссылка на этот репо]

Стек технологий
Backend: Python (Requests, Supabase SDK)

Frontend: React + Vite, Recharts, Tailwind CSS

Database: Supabase (PostgreSQL)

Automation: GitHub Actions

Процесс выполнения (Prompts & Challenges)
Промпты для AI (Cursor/Claude):
"Напиши скрипт на Python, который забирает заказы из RetailCRM API и делает upsert в таблицу orders в Supabase."

"Создай React-дашборд с карточками KPI (выручка, средний чек) и графиком заказов по статусам."

"Добавь в скрипт проверку: если сумма заказа > 50,000 ₸, отправь уведомление через Telegram Bot API."

Где я застрял и как решил:
Ошибка зависимостей: При установке supabase возник конфликт с websockets. Решил обновлением библиотеки pip install --upgrade websockets.

Блокировка Telegram API: Скрипт выдавал TimeoutError при работе локально из-за ограничений сети. Решил проблему использованием VPN (локально) и настройкой GitHub Actions (в облаке), так как сервера GitHub имеют свободный доступ к API Telegram.

Vite Environment Variables: Дашборд сначала не видел ключи Supabase. Узнал, что в Vite переменные должны начинаться строго с префикса VITE_.

Скриншоты
![Уведомление в TG](/screens/tg-noti.png)
![Dashboard](/screens/dashboard.png)
