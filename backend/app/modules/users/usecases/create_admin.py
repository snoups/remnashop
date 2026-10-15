from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role
from app.core.ports import EventPublisher
from app.core.security import generate_password, hash_password
from app.core.security.permissions import Permission, assert_grantable
from app.core.usecase import UseCase
from app.modules.users.dto import AdminWithPasswordDto, CreateAdminDto, CreateUserDto
from app.modules.users.events import AdminCreatedEvent
from app.modules.users.repository import UserRepository


class CreateAdminUseCase(UseCase[CreateAdminDto, AdminWithPasswordDto]):
    required_permission = Permission.ADMINS_MANAGE

    def __init__(
        self,
        user_repository: UserRepository,
        uow: UnitOfWork,
        config: AppConfig,
        event_publisher: EventPublisher,
    ) -> None:
        self._user_repository = user_repository
        self._uow = uow
        self._config = config
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: CreateAdminDto) -> AdminWithPasswordDto:
        assert_grantable(data.permission_grants)
        assert_grantable(data.permission_revokes)

        password = generate_password()
        password_hash = await hash_password(password, self._config.crypt_key.get_secret_value())

        async with self._uow:
            admin = await self._user_repository.create(
                CreateUserDto(
                    login=data.login,
                    password_hash=password_hash,
                    password_change_required=True,
                    name=data.name,
                    role=Role.ADMIN,
                    language=Locale.EN,
                    permission_grants=[p.value for p in data.permission_grants],
                    permission_revokes=[p.value for p in data.permission_revokes],
                )
            )
            await self._event_publisher.publish(
                AdminCreatedEvent(actor=actor, target=admin, ip_address=data.client_ip)
            )

        return AdminWithPasswordDto(admin=admin, password=password)
