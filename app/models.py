from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    login = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)

    games_as_player1 = relationship("Game", foreign_keys="Game.player1_id", back_populates="player1_obj")
    games_as_player2 = relationship("Game", foreign_keys="Game.player2_id", back_populates="player2_obj")
    
    def __repr__(self):
        return f"<Player(id={self.id}, login='{self.login}')>"

class Game(Base):
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    date_created = Column(DateTime, default=datetime.datetime.utcnow)
    date_ended = Column(DateTime, nullable=True)
    desk = Column(JSON, nullable=False)
    player1_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    player2_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    winner_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    current_turn = Column(Integer, nullable=False) 

    player1_obj = relationship("Player", foreign_keys=[player1_id], back_populates="games_as_player1")
    player2_obj = relationship("Player", foreign_keys=[player2_id], back_populates="games_as_player2")
    winner_obj = relationship("Player", foreign_keys=[winner_id])
    
    def __repr__(self):
        return f"<Game(id={self.id}, created={self.date_created}, ended={self.date_ended})>"
