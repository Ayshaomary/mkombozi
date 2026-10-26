# MUKOMBOZI

A web app for small businesses in Tanzania: record sales, track expenses, manage products and stock, see profit and reports, and pay a monthly subscription.

*Programu ya wavuti kwa biashara ndogo Tanzania: rekodi mauzo, fuatilia matumizi, simamia bidhaa na stoki, ona faida na ripoti, na lipia kifurushi cha mwezi.*

| Part | Technology |
|---|---|
| Backend (API) | Python 3.12, Django 6, Django REST Framework, JWT login |
| Database | PostgreSQL 16 (SQLite can be used temporarily) |
| Frontend | React 19, Vite, Tailwind CSS 4, React Router |

## Features

- **Login with phone number.** `0712 345 678`, `255712345678` and `+255712345678` are all treated as the same number.
- **Owner and staff roles.** Staff can record sales and expenses and view products. Only the owner sees profit, edits products, deletes records and pays.
- **Products and stock.** Every stock change (opening stock, purchase, sale, adjustment, return) is recorded with who, when and why.
- **Sales.** Stock goes down automatically, receipts are numbered (`R00001`...), and the buying price at the time of sale is saved so profit stays correct.
- **Payment methods.** Cash, M-Pesa, Mixx by Yas (Tigo Pesa), Airtel Money, HaloPesa, bank and credit (deni).
- **Expenses.** Rent, salaries, transport, electricity and water, and more.
- **Reports.** Revenue, cost of goods sold, gross profit, expenses, net profit, best-selling products, payment methods and sales by day or month.
- **Subscriptions.** A 14-day free trial and 3 plans (monthly, quarterly, yearly). When a subscription ends, the business can still view its data but can't add new records.
- **Languages.** Kiswahili (default) and English. Works on phones, and supports dark mode.

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
| `GET reports/dashboard/` · `GET reports/summary/` | Dashboard · profit & loss report |
| `GET subscription/` · `GET subscription/plans/` · `subscription/payments/` | Subscription |

## Next steps (ideas)

1. **Mobile money payments.** Connect a payment aggregator (e.g. Selcom, AzamPay, ClickPesa) in `subscriptions/views.py`, so payments confirm automatically instead of by an admin.
2. **Customer credit (madeni).** Track who owes money for sales paid on credit.
3. **SMS / WhatsApp receipts** to customers.
4. **Plan limits**, e.g. a maximum number of products or staff per plan.
5. **Deployment** to a server (e.g. Railway, Render or a VPS) with `DEBUG=False`, HTTPS and daily database backups.
# mkombozi
