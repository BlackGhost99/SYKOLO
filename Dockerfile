FROM node:24.11.1-alpine AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend ./frontend
COPY vite.config.mjs ./
RUN npm run build

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY --from=frontend /build/dist ./dist
RUN APP_ENV=test python backend/manage.py check && APP_ENV=test python backend/manage.py test pedagogy && APP_ENV=test python backend/manage.py collectstatic --noinput
RUN useradd --create-home --uid 10001 app
COPY --chmod=755 deploy/start.sh /app/start.sh
USER app
ENV APP_ENV=production PORT=8000
EXPOSE 8000
CMD ["/app/start.sh"]
