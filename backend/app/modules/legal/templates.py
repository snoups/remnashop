"""Starting texts the dashboard offers for an empty document, never shown to customers.

Values in braces are for the shop owner to fill in before saving.
"""

from typing import Final

from app.core.enums import LegalDocumentKind, Locale
from app.modules.legal.dto import LegalTemplateDto

_OFFER_RU: Final[str] = """\
Настоящий документ — публичная оферта {Исполнитель} (далее — Исполнитель) любому лицу (далее — \
Клиент) заключить договор на оказание услуг сервиса {Название сервиса} на условиях ниже. Оплата \
услуги означает полное и безоговорочное принятие оферты.

## 1. Предмет

1.1. Исполнитель предоставляет Клиенту доступ к VPN-сервису на срок и по тарифу, выбранным при \
оплате.
1.2. Тариф определяет срок действия подписки, лимит трафика и количество устройств.
1.3. Услуга считается оказанной с момента выдачи Клиенту ключа подписки.

## 2. Стоимость и оплата

2.1. Стоимость указана в боте и личном кабинете на момент оплаты.
2.2. Оплата принимается через платёжные системы, доступные при оформлении.
2.3. Пробный период, промокоды, реферальные бонусы и скидки предоставляются по правилам, \
действующим на момент их применения, и могут быть изменены Исполнителем.

## 3. Продление и смена тарифа

3.1. Продление прибавляет оплаченный срок к текущему.
3.2. При смене тарифа неиспользованный остаток подписки засчитывается в новый тариф; \
приобретённые дополнения при этом не переносятся.

## 4. Возврат средств

4.1. Клиент может запросить возврат в течение {N} дней после оплаты, написав на {контакты}.
4.2. Возврат производится тем же способом, которым была произведена оплата. После возврата доступ \
к подписке прекращается.

## 5. Ответственность

5.1. Исполнитель не гарантирует доступность конкретных сайтов и сервисов и не отвечает за \
ограничения, введённые третьими лицами, провайдерами или государственными органами.
5.2. Исполнитель не отвечает за перебои, вызванные причинами вне его инфраструктуры.
5.3. Клиент самостоятельно отвечает за соблюдение законодательства при использовании сервиса.

## 6. Реквизиты Исполнителя

{ФИО или наименование}
ИНН: {ИНН}
Контакты: {контакты}
"""

_OFFER_EN: Final[str] = """\
This document is a public offer from {Provider} (the "Provider") to any person (the "Customer") \
to enter into an agreement for the services of {Service name} on the terms below. Paying for the \
service means full and unconditional acceptance of this offer.

## 1. Subject

1.1. The Provider gives the Customer access to a VPN service for the period and plan chosen at \
payment.
1.2. The plan sets the subscription period, the traffic limit and the number of devices.
1.3. The service is considered rendered once the Customer receives the subscription key.

## 2. Price and payment

2.1. The price is shown in the bot and the web cabinet at the time of payment.
2.2. Payment is accepted through the payment systems offered at checkout.
2.3. Trials, promo codes, referral bonuses and discounts follow the rules in force when they are \
applied and may be changed by the Provider.

## 3. Renewal and plan changes

3.1. A renewal adds the paid period to the current one.
3.2. On a plan change the unused remainder is credited to the new plan; purchased add-ons are not \
carried over.

## 4. Refunds

4.1. The Customer may request a refund within {N} days of payment by writing to {contacts}.
4.2. Refunds are made by the same method as the payment. Access to the subscription ends after a \
refund.

## 5. Liability

5.1. The Provider does not guarantee access to any particular website or service and is not \
liable for restrictions imposed by third parties, network operators or authorities.
5.2. The Provider is not liable for outages caused outside its infrastructure.
5.3. The Customer is responsible for complying with the law when using the service.

## 6. Provider details

{Full name or company name}
Tax ID: {tax ID}
Contacts: {contacts}
"""

_USER_AGREEMENT_RU: Final[str] = """\
Соглашение регулирует использование бота и личного кабинета сервиса {Название сервиса}. Начиная \
работу с ботом или входя в кабинет, вы принимаете это соглашение.

## 1. Аккаунт

1.1. Вход возможен через Telegram, внешние сервисы авторизации или код на электронную почту.
1.2. Вы отвечаете за сохранность доступа к аккаунтам, через которые входите.
1.3. По вашему запросу администрация может объединить несколько ваших аккаунтов в один.

## 2. Запрещается

- использовать сервис для незаконной деятельности;
- рассылать спам, проводить атаки на сети и распространять вредоносное ПО;
- передавать или перепродавать ключ подписки третьим лицам сверх лимита устройств;
- обходить технические ограничения сервиса;
- злоупотреблять реферальной программой, промокодами и пробным периодом.

## 3. Нарушения

При нарушении соглашения администрация вправе заблокировать аккаунт и прекратить действие \
подписки без возврата средств.

## 4. Уведомления

Сервисные сообщения о подписке и платежах приходят всегда. От рекламных рассылок можно отписаться \
по ссылке в письме.

## 5. Изменения

Соглашение может меняться. При существенных изменениях вас попросят принять новую редакцию.

## 6. Споры

Споры решаются по законодательству {юрисдикция}. До обращения в суд направьте претензию на \
{контакты}.
"""

_USER_AGREEMENT_EN: Final[str] = """\
This agreement governs the use of the bot and the web cabinet of {Service name}. By starting to \
use the bot or signing in to the cabinet, you accept it.

## 1. Account

1.1. You can sign in with Telegram, an external sign-in provider or a code sent to your email.
1.2. You are responsible for keeping access to the accounts you sign in with.
1.3. On your request the administration can merge several of your accounts into one.

## 2. You must not

- use the service for illegal activity;
- send spam, attack networks or distribute malware;
- share or resell the subscription key beyond the device limit;
- circumvent the technical limits of the service;
- abuse the referral program, promo codes or the trial.

## 3. Violations

If you break this agreement, the administration may block the account and end the subscription \
without a refund.

## 4. Notifications

Service messages about your subscription and payments are always sent. You can unsubscribe from \
marketing emails with the link in the email.

## 5. Changes

This agreement may change. For significant changes you will be asked to accept the new version.

## 6. Disputes

Disputes are governed by the law of {jurisdiction}. Before going to court, send a claim to \
{contacts}.
"""

_PRIVACY_POLICY_RU: Final[str] = """\
Политика описывает, какие данные сервис {Название сервиса} обрабатывает и зачем. Оператор данных \
— {Исполнитель}.

## 1. Какие данные мы собираем

- Telegram ID, имя, имя пользователя и язык интерфейса;
- адрес электронной почты, если вы его указали;
- данные входа через внешние сервисы авторизации;
- IP-адрес и сведения об устройстве при входе в личный кабинет;
- историю покупок и операций, реферальные связи.

## 2. Чего мы не собираем

Мы не храним содержимое трафика и список посещаемых сайтов. Данные банковских карт обрабатывает \
платёжная система, а не мы.

## 3. Зачем

- выдавать и продлевать доступ к сервису;
- принимать оплату и делать возвраты;
- отвечать на обращения в поддержку;
- защищать сервис от злоупотреблений;
- отправлять сервисные уведомления и, с возможностью отписаться, рекламные рассылки.

## 4. Кому мы передаём данные

Платёжным системам, почтовому сервису и Telegram — только в объёме, нужном для работы сервиса. \
Другим лицам — только по требованию закона.

## 5. Сроки хранения

Данные хранятся, пока существует аккаунт. Технические журналы хранятся ограниченное время. При \
удалении аккаунта данные обезличиваются, кроме тех, которые закон обязывает хранить, например \
сведений об оплатах.

## 6. Ваши права

Вы можете узнать, какие данные о вас хранятся, исправить или удалить их и отозвать согласие на \
обработку. Для этого напишите на {контакты}.
"""

_PRIVACY_POLICY_EN: Final[str] = """\
This policy explains what data {Service name} processes and why. The data controller is {Provider}.

## 1. What we collect

- Telegram ID, name, username and interface language;
- your email address, if you provided one;
- sign-in data from external sign-in providers;
- IP address and device details when you sign in to the web cabinet;
- purchase and transaction history, referral links between accounts.

## 2. What we do not collect

We do not store the contents of your traffic or the websites you visit. Card details are \
processed by the payment system, not by us.

## 3. Why

- to give and renew access to the service;
- to accept payments and make refunds;
- to answer support requests;
- to protect the service from abuse;
- to send service notifications and, with the option to unsubscribe, marketing emails.

## 4. Who we share data with

Payment systems, the email service and Telegram, only as far as the service needs. Anyone else \
only when the law requires it.

## 5. Retention

Data is kept while the account exists. Technical logs are kept for a limited time. When an \
account is deleted, its data is anonymized, except what the law requires us to keep, such as \
payment records.

## 6. Your rights

You can find out what data we hold about you, correct or delete it and withdraw your consent to \
its processing. Write to {contacts}.
"""

LEGAL_TEMPLATES: Final[tuple[LegalTemplateDto, ...]] = (
    LegalTemplateDto(
        kind=LegalDocumentKind.OFFER, locale=Locale.RU, title="Публичная оферта", body=_OFFER_RU
    ),
    LegalTemplateDto(
        kind=LegalDocumentKind.OFFER, locale=Locale.EN, title="Public offer", body=_OFFER_EN
    ),
    LegalTemplateDto(
        kind=LegalDocumentKind.USER_AGREEMENT,
        locale=Locale.RU,
        title="Пользовательское соглашение",
        body=_USER_AGREEMENT_RU,
    ),
    LegalTemplateDto(
        kind=LegalDocumentKind.USER_AGREEMENT,
        locale=Locale.EN,
        title="User agreement",
        body=_USER_AGREEMENT_EN,
    ),
    LegalTemplateDto(
        kind=LegalDocumentKind.PRIVACY_POLICY,
        locale=Locale.RU,
        title="Политика конфиденциальности",
        body=_PRIVACY_POLICY_RU,
    ),
    LegalTemplateDto(
        kind=LegalDocumentKind.PRIVACY_POLICY,
        locale=Locale.EN,
        title="Privacy policy",
        body=_PRIVACY_POLICY_EN,
    ),
)
