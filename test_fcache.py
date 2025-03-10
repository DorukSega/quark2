'''Written to test FileCacheManager'''
from modules.fcache import FileCacheManager

def main():
    man = FileCacheManager()
    
    while True:
        user_input = input("Enter file to request or 's' for status: ")
        
        if user_input.lower() == 's':
            man.cache_status()
        else:
            man.request_file(f'data/{user_input}')

if __name__ == "__main__":
    main()