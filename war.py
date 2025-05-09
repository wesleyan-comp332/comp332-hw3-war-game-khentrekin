"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import threading
import sys


"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ["p1", "p2"])

# Stores the clients waiting to get connected to other clients
waiting_clients = []


class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2

def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """
    chunks = [] 
    bytes_recv = 0 

    while bytes_recv < numbytes: 
        chunk = sock.recv(min(numbytes - bytes_recv, 1024)) 
        if not chunk: 
            logging.error("EOF found before numbyptes have been received :(")
        chunks.append(chunk)
        bytes_recv += len(chunk)

    return b''.join(chunks) 


def kill_game(game):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    logging.debug("Killing the game! :(")
    for player in (game.p1, game.p2):
        try:
            player.close() 
        except Exception as e:
            logging.error(f"Error closing client connection: {e}")


def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    # val_g_2 = [0, 13, 26, 39]
    # val_g_3 = [1, 14, 27, 40]
    rank1 = card1 % 13
    rank2 = card2 % 13
    if rank1 < rank2: 
        logging.debug("Card 2 was better")
        return -1
    elif rank1 > rank2:
        logging.debug("Card 1 was better")
        return 1
    else:
        logging.debug("Both cards are the same")
        return 0
    

def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    list_of_cards = []
    for i in range(0, 52):
        list_of_cards.append(i)
    random.shuffle(list_of_cards)
    p1_cards, p2_cards = [], []
    p1_cards = list_of_cards[:26]
    p2_cards = list_of_cards[26:]
    logging.debug("Cards have been dealt! :)")
    return p1_cards, p2_cards

    

def serve_game(host, port):
    """
    TODO: Open a socket for listening for new connections on host:port, and
    perform the war protocol to serve a game of war between each client.
    This function should run forever, continually serving clients.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, port))
        server_sock.listen()
        print(f"Server listening on {host}:{port}")

        waiting_clients = []

        while True:
            client_sock, addr = server_sock.accept()
            print(f"New connection from {addr}")
            waiting_clients.append(client_sock)

            if len(waiting_clients) >= 2:
                logging.debug("Starting the game! :)")
                p1 = waiting_clients.pop(0)
                p2 = waiting_clients.pop(0)
                game = Game(p1, p2)

                # Inline game logic
                def run_single_game(game):
                    try:
                        for player in (game.p1, game.p2):
                            msg = readexactly(player, 2)
                            if len(msg) != 2:
                                return kill_game(game)
                            command, payload = msg
                            if command != Command.WANTGAME.value or payload != 0:
                                return kill_game(game)
                            
                        p1_hand, p2_hand = deal_cards()

                        try:
                            game.p1.sendall(bytes([Command.GAMESTART.value]) + bytes(p1_hand))
                            game.p2.sendall(bytes([Command.GAMESTART.value]) + bytes(p2_hand))
                        except Exception:
                            return kill_game(game)
                        
                        used_card_p1 = set()
                        used_card_p2 = set()

                        for i in range(26):
                            try:
                                message1 = readexactly(game.p1, 2)
                                message2 = readexactly(game.p2, 2)
                                if len(message1) != 2 or len(message2) != 2:
                                    return kill_game(game)
                                command1, card1 = message1
                                command2, card2 = message2
                                if card1 not in p1_hand or card1 in used_card_p1:
                                    return kill_game(game)
                                if card2 not in p2_hand or card2 in used_card_p2:
                                    return kill_game(game)
                                used_card_p1.add(card1)
                                used_card_p2.add(card2)
                                logging.debug("Comparing cards...")
                                result = compare_cards(card1, card2)
                                if result == 1: 
                                    game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.WIN.value]))
                                    game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.LOSE.value]))
                                elif result == -1: 
                                    game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.LOSE.value]))
                                    game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.WIN.value]))
                                else:
                                    game.p1.sendall(bytes([Command.PLAYRESULT.value, Result.DRAW.value]))
                                    game.p2.sendall(bytes([Command.PLAYRESULT.value, Result.DRAW.value]))
                            except Exception:
                                return kill_game(game)
                    except Exception as e:
                        logging.error(f"Game error: {e}")
                        kill_game(game)
                    finally:
                        try: 
                            game.p1.close()
                        except Exception as e:
                            logging.debug(f"Error closing p1 sock: {e}")
                        try:
                            game.p2.close()
                        except Exception as e:
                            logging.debug(f"Error closing p1 sock: {e}")

                    logging.debug("finished game!")
                # Start the game in a new thread
                threading.Thread(target=run_single_game, args=(game,), daemon=True).start()
    

async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)

async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:
        reader, writer = await asyncio.open_connection(host, port)
        # send want game
        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)
        myscore = 0
        for card in card_msg[1:]:
            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)
            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0

def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            # your server should serve clients until the user presses ctrl+c
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    else:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        
        asyncio.set_event_loop(loop)
        
    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]
        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()

if __name__ == "__main__":
    # Changing logging to DEBUG
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1:])