import uuid

from sqlalchemy import (select, Integer, String,
                        Text, Column,
                        DateTime, ForeignKey)

from datetime import datetime

from core.db import AsyncSessionLocal, Base, engine


async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class BaseModel(Base):
    """Base class."""

    __abstract__ = True
    id = Column(Integer(), primary_key=True)


class TelegramUser(BaseModel):
    __tablename__ = 'telegram_users'
    telegram_id = Column(Integer, unique=True)
    chat_id = Column(Integer)
    name = Column(String(200))
    age = Column(Integer())
    city = Column(String(100))
    country = Column(String(100))
    city_lat = Column(String(100))
    city_lon = Column(String(100))
    bio = Column(Text, nullable=True)

    @staticmethod
    async def get_telegram_user(telegram_id: int):
        async with AsyncSessionLocal() as dbsession:
            telegram_user = await dbsession.execute(
                select(TelegramUser)
                .where(TelegramUser.telegram_id == telegram_id))
            return telegram_user.scalars().first()

    @staticmethod
    async def change_name(
            telegram_id: int,
            name: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            user = await dbsession.execute(
                select(TelegramUser)
                .where(TelegramUser.telegram_id == telegram_id))
            user = user.scalars().first()
            user.name = name
            await dbsession.commit()
            return user

    @staticmethod
    async def change_bio(
            telegram_id: int,
            bio: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            user = await dbsession.execute(
                select(TelegramUser)
                .where(TelegramUser.telegram_id == telegram_id))
            user = user.scalars().first()
            user.bio = bio
            await dbsession.commit()
            return user

    @staticmethod
    async def change_age(
            telegram_id: int,
            age: int,
    ):
        async with AsyncSessionLocal() as dbsession:
            user = await dbsession.execute(
                select(TelegramUser)
                .where(TelegramUser.telegram_id == telegram_id))
            user = user.scalars().first()
            user.age = age
            await dbsession.commit()
            return user

    @staticmethod
    async def change_location(
            telegram_id: int,
            city_lat: str,
            city_lon: str,
            city: str,
            country: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            user = await dbsession.execute(
                select(TelegramUser)
                .where(TelegramUser.telegram_id == telegram_id))
            user = user.scalars().first()
            user.city_lat = city_lat
            user.city_lon = city_lon
            user.city = city
            user.country = country

            await dbsession.commit()
            return user

    @staticmethod
    async def add_telegram_user(
            telegram_id: str,
            chat_id: int,
            name: str,
            age: int,
            city: str,
            country: str,
            city_lat: str,
            city_lon: str,
            bio: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            existing_telegram_user = await TelegramUser.get_telegram_user(
                telegram_id=telegram_id)
            if existing_telegram_user:
                return existing_telegram_user
            new_telegram_user = TelegramUser(
                    telegram_id=telegram_id,
                    name=name,
                    age=age,
                    chat_id=chat_id,
                    city=city,
                    country=country,
                    city_lat=city_lat,
                    city_lon=city_lon,
                    bio=bio,
            )
            dbsession.add(new_telegram_user)
            await dbsession.commit()
            await dbsession.refresh(new_telegram_user)
            return new_telegram_user


class Trip(BaseModel):
    __tablename__ = 'trips'
    name = Column(String(200), unique=True)
    trip_org = Column(Integer, ForeignKey('telegram_users.telegram_id'))
    description = Column(Text)

    @staticmethod
    async def get_trip(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(Trip)
                .where(Trip.id == trip_id))
            return trip.scalars().first()

    @staticmethod
    async def get_trip_by_name(trip_name: str):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(Trip)
                .where(Trip.name == trip_name))
            return trip.scalars().first()

    @staticmethod
    async def add_trip(
            name: str,
            description: str,
            trip_org: int,
    ):
        async with AsyncSessionLocal() as dbsession:
            existing_trip = await Trip.get_trip_by_name(
                trip_name=name)
            if existing_trip:
                return existing_trip
            new_trip = Trip(
                    name=name,
                    description=description,
                    trip_org=trip_org,
            )
            dbsession.add(new_trip)
            await dbsession.commit()
            await dbsession.refresh(new_trip)
            await UserTrip.add_user_trip(
                user_id=trip_org,
                trip_id=new_trip.id,
            )
            return new_trip

    @staticmethod
    async def change_name(
            trip_id: int,
            trip_name: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(Trip)
                .where(Trip.id == trip_id))
            trip = trip.scalars().first()
            trip.name = trip_name
            await dbsession.commit()
            return trip

    @staticmethod
    async def change_bio(
            trip_id: int,
            description: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(Trip)
                .where(Trip.id == trip_id))
            trip = trip.scalars().first()
            trip.description = description
            await dbsession.commit()
            return trip

    @staticmethod
    async def delete_trip(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(Trip)
                .where(Trip.id == trip_id))
            trip = trip.scalars().first()
            await dbsession.delete(trip)
            await dbsession.commit()


class UserTrip(BaseModel):
    __tablename__ = 'user_trip'
    user = Column(Integer, ForeignKey('telegram_users.telegram_id'))
    trip = Column(Integer, ForeignKey('trips.id'))

    @staticmethod
    async def get_user_trips(user_id: int):
        async with AsyncSessionLocal() as dbsession:
            trips = await dbsession.execute(
                select(UserTrip)
                .where(UserTrip.user == user_id))
            return trips.scalars().all()

    @staticmethod
    async def get_user_trip(trip_id: int,
                            user_id: int):
        async with AsyncSessionLocal() as dbsession:
            trip = await dbsession.execute(
                select(UserTrip)
                .where(UserTrip.trip == trip_id, UserTrip.user == user_id))
            return trip.scalars().first()

    @staticmethod
    async def get_user_trips_by_trip(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            trips = await dbsession.execute(
                select(UserTrip)
                .where(UserTrip.trip == trip_id))
            return trips.scalars().all()

    @staticmethod
    async def delete_user_trip(
        trip_id: int,
        user: int
    ):
        async with AsyncSessionLocal() as dbsession:
            user_trip = await dbsession.execute(
                select(UserTrip)
                .where(UserTrip.trip == trip_id,
                       UserTrip.user == user))
            user_trip = user_trip.scalars().first()
            await dbsession.delete(user_trip)
            await dbsession.commit()

    @staticmethod
    async def delete_user_trips(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            user_trip = await dbsession.execute(
                select(UserTrip)
                .where(UserTrip.trip == trip_id))
            user_trips = user_trip.scalars().all()
            for user_trip in user_trips:
                await dbsession.delete(user_trip)

            await dbsession.commit()

    @staticmethod
    async def add_user_trip(
            user_id: int,
            trip_id: int,
    ):
        async with AsyncSessionLocal() as dbsession:
            new_user_trip = UserTrip(
                    user=user_id,
                    trip=trip_id,
            )
            dbsession.add(new_user_trip)
            await dbsession.commit()
            await dbsession.refresh(new_user_trip)
            return new_user_trip


class Location(BaseModel):
    __tablename__ = 'locations'
    trip_id = Column(Integer, ForeignKey('trips.id'))
    address = Column(String(300))
    location_lat = Column(String(100))
    location_lon = Column(String(100))
    start = Column(DateTime, default=datetime.now)
    end = Column(DateTime, default=datetime.now)

    @staticmethod
    async def get_locations(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            location = await dbsession.execute(
                select(Location)
                .where(Location.trip_id == trip_id))
            return location.scalars().all()

    @staticmethod
    async def get_location(location_id: int):
        async with AsyncSessionLocal() as dbsession:
            location = await dbsession.execute(
                select(Location)
                .where(Location.id == location_id))
            return location.scalars().first()

    @staticmethod
    async def add_location(
            address: str,
            trip_id: int,
            start: datetime,
            end: datetime,
            location_lat: str,
            location_lon: str,
    ):
        async with AsyncSessionLocal() as dbsession:
            new_location = Location(
                    address=address,
                    trip_id=trip_id,
                    start=start,
                    end=end,
                    location_lat=location_lat,
                    location_lon=location_lon
            )
            dbsession.add(new_location)
            await dbsession.commit()
            await dbsession.refresh(new_location)
            return new_location

    @staticmethod
    async def delete_locations(trip_id: int):
        async with AsyncSessionLocal() as dbsession:
            locations = await dbsession.execute(
                select(Location)
                .where(Location.trip_id == trip_id))
            locations = locations.scalars().all()
            for location in locations:
                await dbsession.delete(location)
            await dbsession.commit()

    @staticmethod
    async def delete_location(location_id: int):
        async with AsyncSessionLocal() as dbsession:
            location = await dbsession.execute(
                select(Location)
                .where(Location.id == location_id))
            location = location.scalars().first()
            await dbsession.delete(location)
            await dbsession.commit()


class Invite(BaseModel):
    __tablename__ = 'invites'
    trip_id = Column(Integer, ForeignKey('trips.id'))
    token = Column(String(300))

    @staticmethod
    async def get_invite(token: str):
        async with AsyncSessionLocal() as dbsession:
            invite = await dbsession.execute(
                select(Invite)
                .where(Invite.token == token))
            invite = invite.scalars().first()
            if not invite:
                return None
            trip_id = invite.trip_id
            await dbsession.delete(invite)
            await dbsession.commit()
            return trip_id

    @staticmethod
    async def add_invite(
            trip_id: int,
    ):
        async with AsyncSessionLocal() as dbsession:
            token = str(uuid.uuid4())
            new_invite = Invite(
                    trip_id=trip_id,
                    token=token
            )
            dbsession.add(new_invite)
            await dbsession.commit()
            await dbsession.refresh(new_invite)
            return new_invite.token


class Note(BaseModel):
    __tablename__ = 'notes'
    location_id = Column(Integer, ForeignKey('locations.id'))
    user_id = Column(Integer, ForeignKey('telegram_users.telegram_id'))
    is_public = Column(Integer)
    file_id = Column(String(200))
    content_type = Column(String(100))

    @staticmethod
    async def get_notes(location_id: int):
        async with AsyncSessionLocal() as dbsession:
            notes = await dbsession.execute(
                select(Note)
                .where(Note.location_id == location_id))
            notes = notes.scalars().all()

            return notes

    @staticmethod
    async def delete_notes(location_id: int):
        async with AsyncSessionLocal() as dbsession:
            notes = await dbsession.execute(
                select(Note)
                .where(Note.location_id == location_id))
            notes = notes.scalars().all()
            for note in notes:
                await dbsession.delete(note)

            await dbsession.commit()

    @staticmethod
    async def delete_notes_user(location_id: int, user_id: int):
        async with AsyncSessionLocal() as dbsession:
            notes = await dbsession.execute(
                select(Note)
                .where(Note.location_id == location_id,
                       Note.user_id == user_id))
            notes = notes.scalars().all()
            for note in notes:
                await dbsession.delete(note)

            await dbsession.commit()

    @staticmethod
    async def add_note(
            location_id: int,
            file_id: str,
            content_type: str,
            is_public: int,
            user_id: int
    ):
        async with AsyncSessionLocal() as dbsession:
            new_note = Note(
                    location_id=location_id,
                    file_id=file_id,
                    content_type=content_type,
                    is_public=is_public,
                    user_id=user_id
            )
            dbsession.add(new_note)
            await dbsession.commit()
            await dbsession.refresh(new_note)

            return new_note
