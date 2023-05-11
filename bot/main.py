from bot import Bot

def main() -> None:
    bot = Bot.create_instance()
    try:
        bot.run()  
    except KeyboardInterrupt:
        pass
    finally:
        bot.loop.run_until_complete(bot.close())
        bot.loop.close()

if __name__ == '__main__':
    main()