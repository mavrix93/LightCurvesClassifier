'''
Created on Nov 2, 2016

@author: Martin Vo
'''

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql.schema import UniqueConstraint

import datetime

from conf import settings

DB_KEY = "og_milli_crossmatch"

def db_connect(db_key):
    return create_engine('sqlite:///' + settings.DATABASES.get( db_key , ""))

Base = declarative_base()

class StarsMO(Base):
    __tablename__ = "StarsMO"
    __table_args__ = {'extend_existing':True}
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    
    name_milliquas = Column( String(35), nullable = True )
    identifier_milliquas = Column( String(50), nullable = True )
    
    name_ogle = Column( String(35), nullable = True )
    identifier_ogle = Column( String(50), nullable = True )
    
    ra_milliquas = Column(Float(10), nullable = True)
    dec_milliquas = Column(Float(12), nullable = True)
    
    ra_ogle = Column(Float(10), nullable = True)
    dec_ogle = Column(Float(12), nullable = True)
    
    angle_dist = Column( Integer )
    
    star_class = Column(String(20), nullable = True)
    
    light_curve = Column( String(100), nullable = True)
    
    uploaded = Column(DateTime, default = datetime.datetime.utcnow )
    
    b_mag_milliquas = Column(Float(10), nullable = True)
    b_mag_ogle = Column(Float(10), nullable = True)
    v_mag_ogle = Column(Float(10), nullable = True)
    i_mag_ogle = Column(Float(10), nullable = True)
    r_mag_milliquas = Column(Float(10), nullable = True)
    
    redshift = Column(Float(4), nullable = True)
    
    lc_n = Column( Integer, nullable = True)
    lc_time_delta = Column( Float(10), nullable = True)
    
    
    UniqueConstraint(name_milliquas, name_ogle, identifier_milliquas, identifier_ogle)
    
    

def update_db( db_key ):
    engine = db_connect( db_key )
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    x_session = DBSession()
    x_session.commit()

update_db( db_key = DB_KEY )  