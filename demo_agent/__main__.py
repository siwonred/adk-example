"""demo_agent 패키지 메인 실행 파일

python -m demo_agent 로 실행할 수 있도록 해주는 파일
"""

import asyncio
from .agent import main

if __name__ == "__main__":
    asyncio.run(main()) 