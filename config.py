"""Конфигурация приложения LUMA."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки из переменных окружения."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    database_url: str = "postgresql+asyncpg://luma:luma@localhost:5432/luma"
    redis_url: str = "redis://localhost:6379/0"
    webapp_url: str = "http://localhost:5173"
    admin_ids: str = ""
    bot_username: str = "luma_bot"
    openai_api_key: str = ""
    sentry_dsn: str = ""
    rules_link_1: str = "https://example.com/rules"
    rules_link_2: str = "https://example.com/privacy"
    webhook_url: str = ""
    webhook_secret: str = ""
    ai_daily_limit: int = 50
    support_fee_rate: float = 0.10
    support_fee_rate_premium: float = 0.02
    withdraw_fee_rate: float = 0.15
    withdraw_fee_rate_premium: float = 0.07
    withdraw_min: int = 1000
    premium_price: int = 249  # совместимость: цена Premium на 1 месяц
    premium_price_1m: int = 249
    premium_price_3m: int = 499
    premium_price_6m: int = 749
    premium_price_12m: int = 1249
    rating_reset_price: int = 50
    event_boost_price: int = 50
    event_pin_price: int = 500
    # Платежи: yookassa | stars (по умолчанию все оплаты идут через ЮKassa)
    payment_provider: str = "yookassa"
    yookassa_shop_id: str = ""
    yookassa_shop_secret_id: str = ""
    yookassa_return_url: str = ""
    spark_price_rub: float = 1.0
    spark_price_stars: float = 1.0

    # Fragment — выплата Stars при выводе Искр
    fragment_ton_seed: str = ""
    fragment_tonapi_key: str = ""
    fragment_wallet_version: str = "V5R1"
    fragment_stel_ssid: str = ""
    fragment_stel_dt: str = "-180"
    fragment_stel_token: str = ""
    fragment_stel_ton_token: str = ""
    fragment_show_sender: bool = False
    fragment_min_stars: int = 50

    # Геокодер Yandex + радиусы поиска «рядом»
    yandex_geocoder_api_key: str = ""
    geo_nearby_radius_km: float = 300.0
    geo_same_city_km: float = 25.0
    geo_http_timeout_sec: float = 3.0
    geo_cache_ttl_fwd_sec: int = 7_776_000  # 90 дней
    geo_cache_ttl_rev_sec: int = 2_592_000  # 30 дней

    @property
    def admin_id_list(self) -> List[int]:
        """Список Telegram ID администраторов."""
        if not self.admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

    @property
    def yookassa_configured(self) -> bool:
        """Есть ли реальные креды ЮKassa."""
        return bool(self.yookassa_shop_id.strip() and self.yookassa_shop_secret_id.strip())

    @property
    def fragment_configured(self) -> bool:
        """Есть ли креды Fragment для автовыплат Stars."""
        return bool(
            self.fragment_ton_seed.strip()
            and self.fragment_tonapi_key.strip()
            and self.fragment_stel_ssid.strip()
            and self.fragment_stel_token.strip()
            and self.fragment_stel_ton_token.strip()
        )

    @property
    def yandex_geocoder_configured(self) -> bool:
        """Есть ли ключ Yandex Geocoder."""
        return bool(self.yandex_geocoder_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Кэшированный экземпляр настроек."""
    return Settings()
