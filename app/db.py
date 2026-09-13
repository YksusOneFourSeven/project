"""Dishka управляет пулом приложения и транзакцией одного HTTP-запроса."""

import os
from collections.abc import AsyncIterator
from dishka import Provider, Scope, provide
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


class DatabaseProvider(Provider):
    @provide(scope=Scope.APP)
    async def pool(self) -> AsyncIterator[AsyncConnectionPool]:
        async with AsyncConnectionPool(
            os.environ["DATABASE_URL"], kwargs={"row_factory": dict_row}, open=False
        ) as pool:
            yield pool

    @provide(scope=Scope.REQUEST)
    async def connection(
        self, pool: AsyncConnectionPool
    ) -> AsyncIterator[AsyncConnection]:
        # Исключение откатывает транзакцию, успешный запрос фиксирует ее.
        async with pool.connection() as conn:
            yield conn


async def rows(conn, query, params=()):
    return await (await conn.execute(query, params)).fetchall()


async def one(conn, query, params=()):
    return await (await conn.execute(query, params)).fetchone()
