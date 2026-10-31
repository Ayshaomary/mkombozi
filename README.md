<img src="frontend/public/logo.svg" alt="SAVIOR Inventory System" width="360">

# SAVIOR Inventory System

> The app was first called MUKOMBOZI (Kiswahili for "savior"). Internal names still use `mukombozi`:
> the Render services and web addresses, the database, the project folder and keys saved in browsers.
> Changing them would break the live site and log everyone out, and users never see them.

A web app for small businesses in Tanzania: record sales, track expenses, manage products and stock, see profit and reports, and pay a monthly subscription.

*Programu ya wavuti kwa biashara ndogo Tanzania: rekodi mauzo, fuatilia matumizi, simamia bidhaa na stoki, ona faida na ripoti, na lipia kifurushi cha mwezi.*

| Part | Technology |
|---|---|
| Backend (API) | Python 3.12, Django 6, Django REST Framework, JWT login |
| Database | PostgreSQL 16 (SQLite can be used temporarily) |
| Frontend | React 19, Vite, Tailwind CSS 4, React Router |

## Features

- **Login with phone number.** `0712 345 678`, `255712345678` and `+255712345678` are all treated as the same number.
- **Forgot password.** A 6-digit code goes to the user's email (Brevo, free) if their profile has one, otherwise by SMS (Beem). Set the keys in `backend/.env` (see `.env.example`). On your computer without SMS keys, the code is shown in the browser instead.
- **Owner and staff roles.** Staff can record sales and expenses and view products. Only the owner sees profit, edits products, deletes records and pays.
- **Products and stock.** Every stock change (opening stock, purchase, sale, adjustment, return) is recorded with who, when and why.
- **Sales.** Stock goes down automatically, receipts are numbered (`R00001`...), and the buying price at the time of sale is saved so profit stays correct.
- **Payment methods.** Cash, M-Pesa, Mixx by Yas (Tigo Pesa), Airtel Money, HaloPesa, bank and credit (deni).
- **Expenses.** Rent, salaries, transport, electricity and water, and more.
- **Reports.** Revenue, cost of goods sold, gross profit, expenses, net profit, best-selling products, payment methods and sales by day or month.
- **Subscriptions.** A 14-day free trial and 3 plans (monthly, quarterly, yearly). When a subscription ends, the business can still view its data but can't add new records.
- **Paying for a subscription.** A payment request to the owner's phone (SonicPesa Push USSD), or a **control number** (ClickPesa BillPay) the owner pays from M-Pesa, Mixx by Yas, Airtel Money, HaloPesa or CRDB. Both activate the subscription as soon as the money arrives. Set the keys in `backend/.env` (see `.env.example`); without them, an admin confirms payments by hand.
- **Languages.** Kiswahili (default) and English. Works on phones, and supports dark mode.

### Automation

- **Recurring expenses.** The owner sets an expense once (e.g. rent TZS 150,000 every month from the 1st), and it's recorded automatically when due. These show an **Otomatiki** badge. If the first date is in the past, missed dates are filled in, up to one year back.
- **Notifications (🔔).**
  - **Low stock / out of stock:** for everyone, the moment stock crosses the warning level or reaches zero.
  - **Daily summary of yesterday:** owner only.
  - **Subscription reminders** at 7, 3 and 1 days before the end, and when it ends: owner only.
  - **Recurring expense recorded:** owner only.

**How the automatic tasks run.** They don't need a server timer. Whenever someone from the business opens the app, missed work is caught up, at most once every 15 minutes. This works on Render's free plan, where the server sleeps. Every task is safe to repeat: nothing is recorded or notified twice. Optionally, a scheduled job (cron) can also run them every morning:

```bash
python manage.py run_automations
```

SMS/WhatsApp alerts can be added later in `notifications/services.py → notify()`, the single place every alert goes through.

## How profit is calculated

```
Revenue (Mapato)          = what customers paid (after discounts)
Gross profit (Faida ghafi) = Revenue − buying cost of the goods sold
Net profit (Faida halisi)  = Gross profit − Expenses
```

Buying stock is **not** recorded as an expense. Its cost is counted when the goods are sold. Counting it as an expense too would subtract the same money twice.

---

## Running the project on your computer

You need 2 terminals: one for the backend and one for the frontend.

### 1. First-time setup: database (once)

```bash
bash backend/scripts/setup_db.sh
```

This creates the PostgreSQL user and database, using the password stored in `backend/.env`. It asks for your Ubuntu (sudo) password.

> **No PostgreSQL yet?** Set `DB_ENGINE=sqlite` in `backend/.env` to use a simple file database for now. Change it back to `DB_ENGINE=postgres` later.

### 2. Backend (terminal 1)

Run these **one at a time**: paste one line, press Enter, and wait for it to finish. If you paste them all at once, `createsuperuser` takes the next lines as its answers.

| Step | Command | What it does |
|---|---|---|
| 1 | `cd ~/Documents/mkombozi/backend` | go to the backend folder |
| 2 | `source venv/bin/activate` | turn on the virtual environment (you'll see `(venv)`) |
| 3 | `python manage.py migrate` | create/update database tables |
| 4 | `python manage.py createsuperuser` | **once only**: an admin account. It asks for phone, first name and password |
| 5 | `python manage.py runserver` | start the API on http://127.0.0.1:8000 |

> **Admin vs shop account.** The superuser is only for the admin panel (`/admin`). It doesn't belong to a business, so use the account you create with **Fungua akaunti** for the app itself. Use a **different phone number** for each: one number = one account.

### 3. Frontend (terminal 2)

```bash
cd frontend
npm install       # first time only
npm run dev       # app on http://localhost:5173
```

Open **http://localhost:5173**, click **Fungua akaunti** and create your business.

### Admin panel

**http://127.0.0.1:8000/admin/** lets you see all businesses, and confirm subscription payments: select them, then use *Actions → Confirm selected payments*.

### Running the tests

```bash
cd backend && source venv/bin/activate
python manage.py test        # backend tests
cd ../frontend
npm run lint && npm run build  # frontend checks
```

---

## Project structure

```
mkombozi/
├── backend/
│   ├── config/          # settings, main URLs, pagination
│   ├── accounts/        # Business, User (phone login), staff, permissions, data separation
│   ├── inventory/       # Category, Product, StockMovement; services.change_stock()
│   ├── sales/           # Sale, SaleItem; services.create_sale() / cancel_sale()
│   ├── expenses/        # Expense
│   ├── reports/         # dashboard and profit & loss (no tables of its own)
│   ├── subscriptions/   # Plan, Subscription (trial), SubscriptionPayment
│   ├── notifications/   # Notification, notify(), automations.py (scheduled tasks), run_automations command
│   ├── scripts/setup_db.sh
│   ├── .env             # secrets - NEVER commit (already in .gitignore)
│   └── .env.example     # list of settings, safe to commit
└── frontend/
    └── src/
        ├── lib/         # api.js (talks to Django), format.js, useApi.js
        ├── context/     # AuthContext (who is logged in)
        ├── i18n/        # translations.js (English + Kiswahili)
        ├── components/  # Layout, BarChart, ui.jsx (buttons, inputs, modals...)
        └── pages/       # one file per screen
```

## API endpoints (all start with `/api/`)

| Endpoint | What it does |
|---|---|
| `POST auth/register/` | Create a business and owner, returns login tokens |
| `POST auth/login/` · `POST auth/refresh/` | Log in with phone + password · refresh token |
| `GET/PATCH auth/me/` · `POST auth/change-password/` | My profile · change password |
| `GET/PATCH business/` | Business details |
| `GET/POST staff/` · `DELETE staff/<id>/` | Staff (owner only) |
| `categories/` · `products/` | Products. Filters: `?search=` `?category=` `?low_stock=true` |
| `POST products/<id>/stock/` | Add or adjust stock |
| `GET stock-movements/?product=<id>` | Stock history |
| `sales/` | Record and list sales. Filters: `?period=today\|week\|month\|year` or `?start=&end=` |
| `expenses/` | Expenses, with the same date filters |
| `recurring-expenses/` | Repeating expenses (owner only) |
| `GET notifications/` · `POST notifications/<id>/read/` · `POST notifications/read-all/` | Notifications. Opening the list also runs the automatic tasks |
| `GET reports/dashboard/` · `GET reports/summary/` | Dashboard · profit & loss report |
| `GET subscription/` · `GET subscription/plans/` · `subscription/payments/` | Subscription |

## Putting it online with Render

The database is on **Neon** (free and permanent). `render.yaml` (a Render "Blueprint") creates the other 2 parts in the Frankfurt region, the closest to Tanzania:

| Name | Where | What | Notes |
|---|---|---|---|
| your Neon project | Neon, AWS Europe Central (Frankfurt) | PostgreSQL database | free: 1 GB, pauses after 5 idle minutes and wakes in about a second |
| `mukombozi-api` | Render | Django API, run by gunicorn | `backend/build.sh` installs packages, collects static files, migrates and creates the admin account |
| `mukombozi` | Render | React website (static site) | forwards `/api/*` to `mukombozi-api`, so no CORS setup is needed |

### Steps

1. Push your code: `git push`
2. Go to **https://neon.tech**, sign up, and create a project in **AWS Europe Central (Frankfurt)**. Click **Connect**, turn **Connection pooling** off, and copy the connection URL.
3. Go to **https://render.com**, sign up with your GitHub account, and allow Render to see the `mkombozi` repository.
4. In the Render dashboard, click **New → Blueprint** and choose the `mkombozi` repository.
5. Render asks for values. Put the Neon URL in `DATABASE_URL`, and fill in the admin account: `DJANGO_SUPERUSER_PHONE` (e.g. `0695517348`), `DJANGO_SUPERUSER_FIRST_NAME` and `DJANGO_SUPERUSER_PASSWORD`. Click **Apply**.
6. Wait 5–10 minutes for the first deploy. Then open the `mukombozi` service and click its URL (e.g. `https://mukombozi.onrender.com`).

> **Check the API address.** `render.yaml` assumes the API's address is `https://mukombozi-api.onrender.com`. If Render gives it a different address (because the name is taken), change the `destination` line in `render.yaml` to match, then commit and push.

After that, every `git push` to `main` deploys again automatically.

### Moving data from a Render database to Neon

The app first used Render's free database, which is deleted 30 days after it was created (plus a 14-day grace period). To copy everything to an empty Neon database and check every table matches:

```bash
bash backend/scripts/copy_db_to_neon.sh
```

It asks for both database addresses (hidden as you paste) and only reads from Render. Then put the Neon URL in **Render → mukombozi-api → Environment → `DATABASE_URL`**.

### Free plan limits (checked October 2026; see render.com/pricing and neon.com/pricing)

- **The Neon free database is permanent** but holds 1 GB and has **no daily backups**. Upgrade before many real shops use the app.
- **The free API sleeps after 15 minutes** without visitors. The next visit takes about a minute to wake it up. To save time, the login page starts waking it as soon as it opens, and someone already logged in sees the app at once with their saved details.
- **The free API gets about a tenth of a CPU.** Passwords are therefore checked with Argon2 at OWASP's settings (`accounts/hashers.py`), which takes about 0.03 seconds of CPU instead of about 1 second for Django's default.
- The static website is free and doesn't sleep.

## Next steps (ideas)

1. **Customer credit (madeni).** Track who owes money for sales paid on credit.
2. **SMS / WhatsApp receipts** to customers.
3. **Plan limits**, e.g. a maximum number of products or staff per plan.
4. **Daily database backups** and a custom domain (e.g. `savior.co.tz`).
