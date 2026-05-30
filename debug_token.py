with open('/home/ubuntu/nanosoft/.env') as f:
    for line in f:
        line = line.strip()
        if 'DISCORD' in line:
            token = line.split('=',1)[1]
            print(f'Token length: {len(token)}')
            print(f'Starts with: {token[:10]}...')
            break
