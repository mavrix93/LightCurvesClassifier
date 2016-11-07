'''
Created on Nov 2, 2016

@author: martin
'''

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from sqlalchemy import Column, ForeignKey, Integer, String, Float, DateTime
from sqlalchemy.sql.schema import UniqueConstraint
from sqlalchemy.orm import relationship

import datetime

from conf import settings

def db_connect(db_key = "local"):
    return create_engine('sqlite:///' + settings.DATABASES.get( db_key , ""))

Base = declarative_base()

class Stars(Base):
    __tablename__ = "Stars"
    __table_args__ = {'extend_existing':True}
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    name = Column( String(35), nullable = True )
    identifier = Column( String(50), nullable = True )
    db_origin = Column(String(20), nullable = True)
    
    ra = Column(Float(10), nullable = True)
    dec = Column(Float(12), nullable = True)
    
    star_class = Column(String(20), nullable = True)
    
    light_curve = Column( String(100), nullable = True)
    
    uploaded = Column(DateTime, default = datetime.datetime.utcnow )
    
    b_mag = Column(Float(10), nullable = True)
    v_mag = Column(Float(10), nullable = True)
    i_mag = Column(Float(10), nullable = True)
    r_mag = Column(Float(10), nullable = True)
    
    redshift = Column(Float(4), nullable = True)
    
    lc_n = Column( Integer, nullable = True)
    lc_time_delta = Column( Float(10), nullable = True)
    
    
    crossmatch_id = Column(Integer, ForeignKey('Stars.id'))
    crossmatch = relationship("Stars", remote_side=[id])
    
    UniqueConstraint(identifier, db_origin, light_curve )
    
    

def update_db( db_key = "local"):
    engine = db_connect( db_key )
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    x_session = DBSession()
    x_session.commit()
    
# update_db()