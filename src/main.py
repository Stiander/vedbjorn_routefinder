"""
    File : main.py
    Author : Stian Broen
    Date : 04.08.2022
    Description :

Entry-point and event-loop for the matching algorithm

"""

# Python libraries
import datetime , time , os

# from matching_library
from libs.matchlib.prepare import organize_reserved_sales , organize_ordinary_sales , organize_routes , \
    organize_drivers
from libs.matchlib.actions import handle_failed_reservations, handle_failed_sales, handle_routes, handle_drives

# from common_library
from libs.commonlib.db_insist import get_db
from libs.commonlib.debug_sim_fullGraph import delete_simulation, simulate_horten_fullGraph, simulate_oslo_fullGraph

from threading import Thread
import asyncio

"""
We need a tiny server, otherwise Google Cloud will complain

Tiny server begin
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
HOST=os.getenv("HOST", "0.0.0.0")
PORT= int(os.getenv("PORT",5678))
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def get_index():
    return {'hello' : 'Im the routefinder server. I have only this function.'}

"""
Tiny server end
"""

ITERATION_SLEEP_TIME  = int(os.getenv('ITERATION_SLEEP_TIME' , 86400))

"""
    Function : iteration

    Description :


"""
def iteration(calc_time : datetime.datetime = datetime.datetime.utcnow()) :

    ok_reservations , failed_reservations = organize_reserved_sales(calc_time)
    handle_failed_reservations(
        ok_reservations     = ok_reservations     ,
        failed_reservations = failed_reservations ,
        calc_time           = calc_time
    )

    ok_sales , failed_sales = organize_ordinary_sales(calc_time)
    handle_failed_sales(
        ok_sales     = ok_sales     ,
        failed_sales = failed_sales ,
        calc_time    = calc_time
    )

    combined_sales = ok_reservations
    combined_sales.extend(ok_sales)
    if len(combined_sales) <= 0 :
        return

    ok_drives , failed_drives = organize_drivers(calc_time)
    handle_drives(
        ok_drives     = ok_drives     ,
        failed_drives = failed_drives ,
        calc_time     = calc_time
    )

    routes = organize_routes(calc_time)
    handle_routes(
        routes    = routes    ,
        calc_time = calc_time ,
        is_fake   = True
    )

"""

    Function : save_guide

    Description :

"""
def save_guide(guide : dict) :
    guide['saved'] = datetime.datetime.utcnow().timestamp()
    db = get_db()
    if '_id' in guide :
        db.insist_on_replace_one('matchloop_guide' , guide['_id'], guide)
    else:
        db.insist_on_insert_one('matchloop_guide', guide)


"""

    Function : check_guide

    Description :
        This function will try to find a "guide" document in the database, which it can use to determine whether or not
        a matching-iteration should take place.
        
    Returns : bool (should run iteration? yes or no) , dict (the guide document, which may potentially contain information
              which is useful for the iteration)

"""
def check_guide() -> tuple :
    db = get_db()

    seasonInfo = db.insist_on_find_most_recent('season')
    if seasonInfo:
        in_season = seasonInfo.get('status', 'on') == 'on'
        if not in_season :
            print('OFF-SEASON')
            return False , {}

    guide_doc = db.insist_on_find_one_q('matchloop_guide' , {})
    if not guide_doc :
        """
            Situation 1 : There is no guide! Then an iteration should definitely take place
        """
        return True , {}
    _now = datetime.datetime.utcnow().timestamp()
    if _now - guide_doc.get('saved' , 0) > ITERATION_SLEEP_TIME :
        """
            Situation 2 : There has been an hour since the last iteration, its time to do it again
        """
        return True , guide_doc
    if guide_doc.get('graph_changed' , False) == True :
        """
            Situation 3 : If there has been a change in the graph, it should calculate again
        """
        db.insist_on_update_one(guide_doc , 'matchloop_guide', 'graph_changed' , False)
        guide_doc['graph_changed'] = False
        return True , guide_doc

    """
        Situation default : There is no need to do anything
    """
    return False , guide_doc

def routefinder_loop(asyncLoop) :
    """

    :param asyncLoop:
    :return:
    """
    asyncio.set_event_loop(asyncLoop)
    while True :
        should_calc , guide_doc = check_guide()
        if should_calc :
            print('\t\tNEW ITERATION TRIGGERED.')
            calc_time = datetime.datetime.utcnow()
            iteration(calc_time)
            print('\t\tNEW ITERATION FINISHED.')
            save_guide(guide_doc)
        time.sleep(10)

"""

    __main__

    Description :


"""
if __name__ == '__main__':
    print('###############################')
    print('#')
    print('#       Service ROUTE-FINDER - BEGINS')
    print('#')
    print('#\tTime : ' , datetime.datetime.utcnow())
    print('#')
    print('#')

    #delete_simulation()
    #simulate_horten_fullGraph()
    #simulate_oslo_fullGraph()

    """
    Start the thread which actually does something
    """
    asyncLoop = asyncio.new_event_loop()
    _thread = Thread(target=routefinder_loop, args=(asyncLoop,))
    _thread.start()

    """
    Start the tiny server.
    """
    uvicorn.run('main:app', host=HOST, port=PORT)
