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

def db_connect():
    return create_engine('sqlite:///' + settings.DB_FILE_PATH)

Base = declarative_base()


class Stars(Base):
    __tablename__ = "Stars"
    __table_args__ = {'extend_existing':True}
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    name = Column( String(50), nullable = True )
    identifier = Column( String(50), nullable = True )
    db_origin = Column(String(50), nullable = True)
    
    ra = Column(Float(10), nullable = True)
    dec = Column(Float(10), nullable = True)
    
    star_class = Column(String(20), nullable = True)
    
    light_curve = Column( String(100), nullable = True)
    
    uploaded = Column(DateTime, default = datetime.datetime.utcnow )
    
    b_mag = Column(Float(10), nullable = True)
    v_mag = Column(Float(10), nullable = True)
    i_mag = Column(Float(10), nullable = True)
    
    lc_n = Column( Integer, nullable = True)
    lc_time_delta = Column( Float(10), nullable = True)
     
    crossmatch_id = Column(Integer, ForeignKey('Stars.id'))
    crossmatch = relationship("Stars", remote_side=[id])
    


def update_db():
    engine = db_connect()
    Base.metadata.create_all(engine)
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    x_session = DBSession()
    x_session.commit()
    
update_db()