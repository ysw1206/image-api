# Gemini Image Generation API Plan

## Task Definition
plan task: 나노바나나(Gemini) 이미지 생성 Python API 서버 설계 및 PoC

## 배경/목표
/generate-image 엔드포인트로 프롬프트를 받아 Gemini API를 통해 이미지 생성 후 S3에 업로드하고 URL 반환

## 스택/제약
- Python 3.11+
- FastAPI
- httpx (비동기 HTTP)
- boto3 (S3)
- python-dotenv
- 환경변수로 API 키/S3 설정 관리
- 구조화된 로깅(logging)
- 예외 처리
- pytest로 유닛테스트

## 예상 소요시간
4-6시간

## 산출물
- src/main.py (FastAPI 앱)
- src/routes/image_routes.py (엔드포인트 정의)
- src/services/gemini_client.py (Gemini API 클라이언트)
- src/services/s3_client.py (S3 업로드 로직)
- src/config.py (환경변수 관리)
- tests/test_image_generation.py (유닛테스트)
- Dockerfile
- .env.example
- README.md (설치/실행/API 사용법)
- 예제 curl 커맨드

## 우선순위
1. 프로젝트 구조 및 설정 (config, .env)
2. GET /healthz 엔드포인트
3. Gemini API 클라이언트 구현
4. S3 업로드 클라이언트 구현
5. POST /generate-image 엔드포인트 통합
6. 예외 처리 및 로깅
7. 유닛테스트 작성
8. Dockerfile 작성
9. README 및 문서화

## 의존성
- Gemini API 키
- AWS S3 버킷 및 IAM 권한 설정 완료 필요

## 테스트 기준
- 2개 이상의 서로 다른 프롬프트로 실제 이미지 생성 성공 확인
- 잘못된 요청(빈 프롬프트, 필수 파라미터 누락) 시 400 에러 반환
- Gemini API 실패 시 500 에러 및 적절한 에러 메시지 반환
- S3 업로드 실패 시 에러 핸들링 확인
- 모든 주요 동작에 대한 로그 출력 확인
- /healthz 엔드포인트 200 응답 확인