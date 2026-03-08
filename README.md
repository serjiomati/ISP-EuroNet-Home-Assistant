# ISP EuroNet Home Assistant

Кастомна інтеграція Home Assistant для особистого кабінету ISP EuroNet.

## Що додає

Після налаштування з'являються 3 сенсори (для кожного логіна `_uu`):

1. `sensor.isp_euronet_<login>_euronet_balance` — активний баланс.
2. `sensor.isp_euronet_<login>_euronet_next_write_off_amount` — наступна сума списання.
3. `sensor.isp_euronet_<login>_euronet_next_write_off_date` — дата/час наступного списання.

Наприклад для логіна `190`:

- `sensor.isp_euronet_190_euronet_balance`
- `sensor.isp_euronet_190_euronet_next_write_off_amount`
- `sensor.isp_euronet_190_euronet_next_write_off_date`

## Налаштування

1. Скопіюйте `custom_components/isp_euronet` у вашу папку `config/custom_components`.
2. Перезапустіть Home Assistant.
3. В Home Assistant: **Settings → Devices & Services → Add Integration**.
4. Знайдіть **ISP EuroNet**.
5. Введіть:
   - `login` = значення `_uu`
   - `password` = значення `_pp`

Інтеграція авторизується, зберігає cookie `noses` і автоматично оновлює сесію кожні ~7200 секунд.

## Базовий приклад (Entities card)

```yaml
type: entities
title: ISP EuroNet (190)
entities:
  - entity: sensor.isp_euronet_190_euronet_balance
    name: Баланс
  - entity: sensor.isp_euronet_190_euronet_next_write_off_amount
    name: Наступне списання
  - entity: sensor.isp_euronet_190_euronet_next_write_off_date
    name: Дата списання
```

## Сучасна картка (Mushroom, 1 стильний блок)

> Потрібен HACS + `Mushroom Cards`.

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-title-card
    title: ISP EuroNet
    subtitle: Особовий рахунок 190

  - type: custom:mushroom-template-card
    entity: sensor.isp_euronet_190_euronet_balance
    primary: >-
      Баланс: {{ states('sensor.isp_euronet_190_euronet_balance') }} грн
    secondary: >-
      Наступне списання: {{ states('sensor.isp_euronet_190_euronet_next_write_off_date') }}
      · {{ states('sensor.isp_euronet_190_euronet_next_write_off_amount') }} грн
    multiline_secondary: true
    icon: mdi:wallet-outline
    icon_color: >-
      {% set b = states('sensor.isp_euronet_190_euronet_balance') | float(0) %}
      {{ 'green' if b >= 100 else 'amber' if b >= 0 else 'red' }}
    badge_icon: mdi:cash-clock
    badge_color: blue
    tap_action:
      action: more-info

  - type: custom:mushroom-chips-card
    chips:
      - type: template
        icon: mdi:web
        content: >-
          {{ state_attr('sensor.isp_euronet_190_euronet_balance','service_title') or 'Послуга ISP EuroNet' }}
      - type: template
        icon: mdi:cash-fast
        content: >-
          {{ states('sensor.isp_euronet_190_euronet_next_write_off_amount') }} грн
```

## Де подивитися всі послуги

У кожного сенсора є атрибут `services` (масив), наприклад:

- `services[].title`
- `services[].next_service_price`
- `services[].time_left`
- `services[].human_time`
- `services[].billing_at`
- `services[].description`

## Технічні деталі

- Авторизація: `GET /cgi-bin/noapi.pl?_uu=<login>&_pp=<password>`
- Дані: `GET /cgi-bin/noapi.pl?a=u_main` з cookie `noses=<session>`
- Частота оновлення в HA: кожні 5 хвилин.
