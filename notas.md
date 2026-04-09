http://localhost:8000/confirm-email/dXZ16sRbIlOh5p5yaSTRHYPoe9a4ndJjmbxVWtgOOAU

adb shell am start -W -a android.intent.action.VIEW -d "oppychat://confirm-success?token=TU_TOKEN" com.example.oppy2_frontend

http://localhost:8000/confirm-email/rlYdXUpLTU1tZI_h81qaVWrhoDS8BZjTc5Qup38naYc

adb shell am start -W -a android.intent.action.VIEW -d "oppychat://confirm-success?token=rlYdXUpLTU1tZI_h81qaVWrhoDS8BZjTc5Qup38naYc" com.example.oppy2_frontend

adb shell am start -W -a android.intent.action.VIEW -d "oppychat://confirm-success?token=1ifqiKUE6WsBJwDDfgVItwrwOWJ1V5OdKvc0iEwBW2w" com.example.oppy2_frontend

http://localhost:8000/confirm-email/1ifqiKUE6WsBJwDDfgVItwrwOWJ1V5OdKvc0iEwBW2w



# ALEMBIC

docker exec -it chat-backend alembic revision --autogenerate -m "add Tags Escenario Tables Avatars"

docker exec -it chat-backend alembic upgrade head



