import sys
import ac
import acsys
import os
import platform

if platform.architecture()[0] == "64bit":
    sysdir = "stdlib64"
else:
    sysdir = "stdlib"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), sysdir))
os.environ['PATH'] = os.environ['PATH'] + ";."

import socket

deltaT = 2500
carsInSession = 0
carsInSessionLabel = 0
driverNamesLabel = []
driverPositionLabel = []
driverID = []


class driver:
    def __init__(self, id, driverName, carName):
        self.id = id
        self.driverName = driverName
        self.carName = carName
        self.lapCount = 0
        self.leaderboardPosition = 0
        self.delta = 0.000
        self.onTrack = 1
        self.raceStarted = 0
        self.lastSplineForStart = 999
        self.fastestLap = 0


def acMain(ac_version):
    global sock, server_address, driverList, lastSpline, sessionLive, resetFlag
    sessionLive = False
    resetFlag = False
    driverList = []
    lastSpline = 0.000

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('127.0.0.1', 9090)

    appWindow = ac.newApp("TCR Overlay")
    ac.console("Overlay compatible: V2.1.0")
    ac.setSize(appWindow, 200, 600)

    # Generate initial driver list
    i = 0
    while i < ac.getCarsCount():
        driverList.append(driver(i, ac.getDriverName(i), ac.getCarName(i)))
        driverList[i].leaderboardPosition = ac.getCarRealTimeLeaderboardPosition(i) + 1
        i += 1

    return "TCR Overlay"


def acUpdate(deltaT):
    global driverList, lastSpline, sessionLive, resetFlag

    sendString = ""
    i = 0
    leaderID = 0

    # Check for new drivers
    # TODO

    # Get leaders carID
    while i < ac.getCarsCount():
        if ac.getCarRealTimeLeaderboardPosition(i) == 0:
            leaderID = i
            driverList[leaderID].delta = 0.000
        i += 1

    # Update driver info only every 5% of track length
    if abs(lastSpline - (ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition) + ac.getCarState(leaderID, acsys.CS.LapCount))) > 0.03:
        if ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition) > 0.05 and ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition) < 0.95:
            estLeaderTime = (ac.getCarState(leaderID, acsys.CS.LapTime) / 1000) / ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition)

            for driver in driverList:
                relativeDistance = (ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition) + ac.getCarState(leaderID, acsys.CS.LapCount)) - (ac.getCarState(driver.id, acsys.CS.NormalizedSplinePosition) + ac.getCarState(driver.id, acsys.CS.LapCount))
                delta = relativeDistance * estLeaderTime
                driver.delta = delta

                if ac.isCarInPitline(driver.id) == 1 or ac.isCarInPit(driver.id) == 1:
                    driver.onTrack = 0
                else:
                    driver.onTrack = 1
                driver.leaderboardPosition = ac.getCarRealTimeLeaderboardPosition(driver.id) + 1

            lastSpline = ac.getCarState(leaderID, acsys.CS.NormalizedSplinePosition) + ac.getCarState(leaderID,
                                                                                                      acsys.CS.LapCount)

    # Start session when driver crosses the line (For normal Race sessions)
    for driverSession in driverList:
        if driverSession.raceStarted == 0 and ac.getCarState(driverSession.id, acsys.CS.NormalizedSplinePosition) != 0.0:
            if ac.getCarState(driverSession.id, acsys.CS.NormalizedSplinePosition) > 0.5:
                driverSession.lastSplineForStart = ac.getCarState(driverSession.id, acsys.CS.NormalizedSplinePosition)

            if ac.getCarState(driverSession.id, acsys.CS.NormalizedSplinePosition) < 0.1:
                driverSession.raceStarted = 1
                ac.console("Race Started")

        # Set Session live flag if the driver has already completed a lap.
        # Note, this is not sent to UDP, and is used to restrict reset flag being sent
        if not sessionLive:
            if ac.getCarState(driverSession.id, acsys.CS.BestLap) != 0 and driverSession.raceStarted == 1:
                sessionLive = True
                ac.console("Session Live")

    # Checks drivers best laps
    # if best lap is 0 for all drivers, reset flag is set true to get overlay to trigger next timer
    for driverReset in driverList:
        driverReset.fastestLap = ac.getCarState(driverReset.id, acsys.CS.BestLap)
        if sessionLive:
            if driverReset.fastestLap != 0:
                resetFlag = False
                break
            else:
                resetFlag = True

    # If Reset flag is true, set reset trigger, default flags, and default driver data
    if sessionLive:
        if resetFlag:
            sessionLive = False
            resetFlag = False
            ac.console("Session Reset")
            for driverDefault in driverList:
                driverDefault.lapCount = 0
                driverDefault.delta = 0.000
                driverDefault.lastSplineForStart = 999
                driverDefault.raceStarted = 0

    # Build and send datagram
    for driverDatagram in driverList:
        driverDatagram.lapCount = ac.getCarState(driverDatagram.id, acsys.CS.LapCount)

        sendString = sendString + str(driverDatagram.id) + ";"
        sendString = sendString + driverDatagram.driverName + ";"
        sendString = sendString + str(driverDatagram.lapCount) + ";"
        sendString = sendString + ac.getDriverName(ac.getFocusedCar()) + ";"
        sendString = sendString + driverDatagram.carName + ";"
        sendString = sendString + str(format(driverDatagram.delta, ".3f")) + ";"
        sendString = sendString + str(driverDatagram.onTrack) + ";"
        sendString = sendString + str(driverDatagram.raceStarted) + ";"
        sendString = sendString + str(driverDatagram.leaderboardPosition) + ":"

    sock.sendto(sendString.encode(), server_address)

    # TODO Add session start flag for practice and qualifying