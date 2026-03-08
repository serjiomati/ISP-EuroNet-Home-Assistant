# ISP EuroNet Home Assistant

Кастомна інтеграція Home Assistant для особистого кабінету ISP EuroNet.

## Що додає

Після налаштування з'являються 3 сенсори:

1. `sensor.euronet_balance` — активний баланс.
2. `sensor.euronet_next_write_off_amount` — наступна сума списання.
3. `sensor.euronet_next_write_off_date` — дата/час наступного списання.

## Налаштування

1. Скопіюйте `custom_components/isp_euronet` у вашу папку `config/custom_components`.
2. Перезапустіть Home Assistant.
3. В Home Assistant: **Settings → Devices & Services → Add Integration**.
4. Знайдіть **ISP EuroNet**.
5. Введіть:
   - `login` = значення `_uu`
   - `password` = значення `_pp`

Інтеграція авторизується, зберігає cookie `noses` і автоматично оновлює сесію кожні ~7200 секунд.

## Приклад віджета (Entities card)

```yaml
type: entities
title: ISP EuroNet
entities:
  - entity: sensor.euronet_balance
    name: Баланс
  - entity: sensor.euronet_next_write_off_amount
    name: Наступне списання
  - entity: sensor.euronet_next_write_off_date
    name: Дата списання
```

## Технічні деталі

- Авторизація: `GET /cgi-bin/noapi.pl?_uu=<login>&_pp=<password>`
- Дані: `GET /cgi-bin/noapi.pl?a=u_main` з cookie `noses=<session>`
- Частота оновлення в HA: кожні 5 хвилин.


## Сучасна 1-card картка (Mushroom)

> Потрібен HACS + `Mushroom Cards`.

```yaml
type: custom:mushroom-template-card
entity: sensor.euronet_balance
primary: "Баланс: {{ states('sensor.euronet_balance') }} грн"
secondary: >-
  Списання: {{ states('sensor.euronet_next_write_off_date') }}
  · {{ states('sensor.euronet_next_write_off_amount') }} грн
multiline_secondary: true
icon: mdi:wallet
icon_color: >-
  {% set b = states('sensor.euronet_balance') | float(0) %}
  {{ 'green' if b >= 0 else 'red' }}
badge_icon: mdi:cash-clock
badge_color: blue
```

## Де подивитися всі послуги

У кожного сенсора є атрибут `services` (масив), наприклад:

- `services[].title`
- `services[].next_service_price`
- `services[].human_time`
- `services[].description`

Можна вивести в markdown-картці через шаблон.
