from storage.engine import CollectionStore, NOW

CollectionName = 'counters'

_store = CollectionStore(
    name=CollectionName,
    defaults={},
    unique_sets=[],
    json_fields=set([]),
    datetime_fields=set([]),
    sequence_fields={},
    update_cache=('counters_cache', ['guild_id']),
    delete_cache=('counters_cache', ['guild_id']),
)

async def create_table():
    return await _store.prepare()

async def insert(

    id:int=None,
    guild_id:int=None,
    enabled:bool=None,
    member_counter_channel_id:int=None,
    bot_counter_channel_id:int=None,
    boost_counter_channel_id:int=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.insert(locals())

async def update(

    id:int,
    guild_id:int=None,
    enabled:bool=None,
    member_counter_channel_id:int=None,
    bot_counter_channel_id:int=None,
    boost_counter_channel_id:int=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.update(locals())

async def get(

    id:int=None,
    guild_id:int=None,
    enabled:bool=None,
    member_counter_channel_id:int=None,
    bot_counter_channel_id:int=None,
    boost_counter_channel_id:int=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.get(locals())

async def gets(

    id:int=None,
    guild_id:int=None,
    enabled:bool=None,
    member_counter_channel_id:int=None,
    bot_counter_channel_id:int=None,
    boost_counter_channel_id:int=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.gets(locals())

async def delete(

    id:int=None,
    guild_id:int=None,
    enabled:bool=None,
    member_counter_channel_id:int=None,
    bot_counter_channel_id:int=None,
    boost_counter_channel_id:int=None,
    updated_at:str=None,
    created_at:str=None
):
    return await _store.delete(locals())

async def get_all():
    return await _store.get_all()
