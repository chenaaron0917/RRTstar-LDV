import openravepy
import random
import math
import copy
import numpy as np
import matplotlib.pyplot as plt
import time

class Node():
    def __init__(self,q):
        self.q=q
        self.cost=0.0
        self.parent=None
        self.visibility = float('inf')

class FailNode():
    def __init__(self,q):
        self.q = q
        self.imp = float('inf')

class RRTStar():
    def __init__(self, env, robot, start, goal, lowerlimits, upperlimits, goalBias=10 ,steersize=0.3):
        self.env=env
        self.robot=robot
        self.DOF=len(start)
        self.start=Node(start)
        self.goal=Node(goal)

        self.lowerlimits=lowerlimits
        self.upperlimits=upperlimits

        self.goalBias=goalBias
        self.steersize=steersize
        self.checksize=0.2

        self.failSparsity=0.1

        self.samplingStrategyBias=40
        self.maxIter=500
        self.r=self.steersize

    def RRTSearch(self, animation=1):
        timestart = time.time()
        timenow = 0.0
        allcosts = []
        alltimes = []
        random.seed(0)
        firstFound = False
        self.nodeTree=[]
        self.nodeTree.append(self.start)
        self.failNodes=[]
        for i in range(self.maxIter):
            if firstFound:
                self.goalBias = -1
                if self.failNodes and random.randint(0, 100) > self.samplingStrategyBias:
                    rndQ = self.get_point_around_failnodes()
                    #rndQ = self.get_random_point()
                else:  # rnegular sampling strategy
                    rndQ = self.get_random_point()
            else:
                rndQ = self.get_random_point()         
            minidx = self.GetNearestListIndex(rndQ)
            newNode = self.steer(rndQ, minidx)

            if self.__CollisionCheck(newNode):
                nearinds = self.find_near_nodes(newNode)
                newNode = self.choose_parent(newNode, nearinds)
                if newNode.parent == None:
                    pass
                else:
                    self.nodeTree.append(newNode)
                    #if not firstFound:
                    self.update_failNodes(newNode)
                    self.rewire(newNode, nearinds, minidx)
            if animation and i % 5 == 0:
                self.DrawGraph(rndQ)

            if not firstFound and i % 10 == 0:
                #lastIndex =self.get_best_last_index()
                bestpath, minpathcost = self.get_best_last_index()
                if bestpath is None:
                #if lastIndex is None:
                    firstFound = False
                else:
                    firstFound = True
                    allcosts.append(minpathcost)
                    firstIter = i
                    timenow = time.time() - timestart
                    alltimes.append(timenow)
                    print "First Found! Iter: "+ str(i)+". Cost: "+ str(minpathcost) + ". Time: " + str(timenow)

            if firstFound and i % 50 == 0:
                bestpath, minpathcost = self.get_best_last_index()
                allcosts.append(minpathcost)
                timenow = time.time() - timestart
                alltimes.append(timenow)
                print "Iter: "+str(i)+". Cost: "+str(minpathcost)
                

        bestpath, minpathcost = self.get_best_last_index()
        allcosts.append(minpathcost)
        timenow = time.time() - timestart
        print "Time: " + str(timenow)
        return bestpath, allcosts, alltimes, len(self.nodeTree)

    def update_failNodes(self, newNode):
        if newNode.parent == None:
            pass
        else:
            uniDir,_ = self.computeUniDir(self.nodeTree[newNode.parent].q, newNode.q)
            step = 0
            tmpNode = copy.deepcopy(newNode)
            while self.__CollisionCheck(tmpNode):
                for i in range(self.DOF):
                    tmpNode.q[i] += self.failSparsity * uniDir[i]
                step += 1
            step -= 1
            failNodeQ = []
            for i in range(self.DOF):
                failNodeQ.append(newNode.q[i] + step * self.failSparsity * uniDir[i])
            
            if not self.failNodes:
                failNode = FailNode(failNodeQ)
                self.failNodes.append(failNode)
            else:
                mindist = self.GetNearestNeighborDist(failNodeQ)
                if  mindist>self.failSparsity:
                    failNode = FailNode(failNodeQ)
                    self.failNodes.append(failNode)
        

    def computeDistance(self, qFrom, qTo): # get distance between two configs
        dist = 0
        for i in range(self.DOF):
            dist += (qTo[i]-qFrom[i])**2
        return math.sqrt(dist)

    def computeUniDir(self,qFrom,qTo): # get univector from.. to..
        uniDir=[]
        dist = self.computeDistance(qFrom,qTo)
        for i in range(self.DOF):
            uniDir.append((qTo[i]-qFrom[i])/dist)
        return uniDir, dist

    def choose_parent(self, newNode, nearinds):
        if not nearinds:
            return newNode

        dlist = []
        for i in nearinds:
            nearNode = self.nodeTree[i]
            #d = self.computeDistance(nearNode.q, newNode.q)
            uniDir,d = self.computeUniDir(nearNode.q, newNode.q)
            if self.check_collision_extend(nearNode, uniDir, d):
                nearNode.cost=self.cal_cost2come(i)
                dlist.append(nearNode.cost + d)
            else:
                dlist.append(float("inf"))

        mind = min(dlist)
        minind = nearinds[dlist.index(mind)]

        if mind == float("inf"):
            #print("mind is inf")
            newNode.parent = None
            return newNode

        newNode.cost = mind
        newNode.parent = minind

        return newNode

    def steer(self, rndQ, minidx):

        # expand tree
        nearestNode = self.nodeTree[minidx]
        uniDir, currentDistance = self.computeUniDir(nearestNode.q, rndQ)
        currentDistance = self.computeDistance(nearestNode.q, rndQ)
        newNode = Node(rndQ)
        # Find a point within expandDis of nind, and closest to rnd
        if currentDistance <= self.steersize:
            newNode.cost = nearestNode.cost + currentDistance
        else:
            for i in range(self.DOF):
                newNode.q[i] = nearestNode.q[i] + self.steersize * uniDir[i]
        newNode.cost = nearestNode.cost + self.steersize
        newNode.parent = minidx
        return newNode

    def get_point_around_failnodes(self):
        a = random.randint(0, len(self.failNodes)-1)
        failrndNode = self.failNodes[a]
        randsize = self.steersize*self.failSparsity*10

        rndQ = []
        for i in range(self.DOF):
            rndQ.append(failrndNode.q[i]+random.uniform(-randsize, randsize))

        while not self.__CollisionCheckQ(rndQ):
            rndQ = []
            for i in range(self.DOF):
                rndQ.append(failrndNode.q[i]+random.uniform(-randsize, randsize))

        return rndQ

    def get_random_point(self):
        rndQ=[]
        if random.randint(0, 100) > self.goalBias:
            for i in range(self.DOF):
                rndQ.append(random.uniform(self.lowerlimits[i], self.upperlimits[i]))
        else:  # goal point sampling
            for i in range(self.DOF):
                rndQ.append(self.goal.q[i])

        return rndQ

    def get_best_last_index(self):

        disglist = [self.calc_dist_to_goal(node.q) for node in self.nodeTree]
        goalinds = [disglist.index(i) for i in disglist if i <= 0]

        if not goalinds:
            return None, float("inf")

        pathcost = []
        path = []
        for j in range(len(goalinds)):
            path.append(self.gen_final_course(goalinds[j]))
            pathcost.append(self.cal_totalcost(path[j]))

        mincost = min(pathcost)
        for j in range(len(goalinds)):
            if pathcost[j] == mincost:
                return path[j], mincost

        return None, float("inf")

    def gen_final_course(self, goalind):
        path = []
        goalconfig = []
        for i in range(self.DOF):
            goalconfig.append(self.goal.q[i])
        path.append(goalconfig)
        while self.nodeTree[goalind].parent is not None:
            node = self.nodeTree[goalind]
            nodeconfig = []
            for i in range(self.DOF):
                nodeconfig.append(node.q[i])
            path.append(nodeconfig)
            goalind = node.parent
        startconfig = []
        for i in range(self.DOF):
            startconfig.append(self.start.q[i])
        path.append(startconfig)
        path.reverse()
        return path

    def cal_cost2come(self, ind):
        path=[]
        while self.nodeTree[ind].parent is not None:
            node = self.nodeTree[ind]
            nodeconfig = []
            for i in range(self.DOF):
                nodeconfig.append(node.q[i])
            path.append(nodeconfig)
            ind = node.parent
        path.reverse()
        cost2come=self.cal_totalcost(path)
        return cost2come

    def cal_totalcost(self, path):
        totalcost = 0.0
        for i in range(len(path)):
            if i!= (len(path)-1):
                dist=self.computeDistance(path[i], path[i+1])
                totalcost += dist
                #totalcost += math.sqrt ((path[i][0]-path[i+1][0])**2 + (path[i][1]-path[i+1][1])**2)
        return totalcost

    def calc_dist_to_goal(self, q):
        return self.computeDistance(q, self.goal.q)

    def find_near_nodes(self, newNode):
        nnode = len(self.nodeTree)
        self.r = min(50.0 * (math.log(nnode) / nnode)**(1.0/self.DOF), self.steersize)
        #  r = self.expandDis * 5.0
        dlist = []
        for node in self.nodeTree:
            dist = 0.0
            for i in range(self.DOF):
                dist += (node.q[i] - newNode.q[i])**2
            dlist.append(dist)
        nearinds = [dlist.index(i) for i in dlist if i <= self.r ]
        return nearinds

    def rewire(self, newNode, nearinds, minind):
        nnode = len(self.nodeTree)
        for i in nearinds:
            if i!=minind:
                nearNode = self.nodeTree[i]
                d = self.computeDistance(nearNode.q, newNode.q)
                scost = newNode.cost + d               
                if nearNode.cost > scost:
                    uniDir,_ = self.computeUniDir(nearNode.q, newNode.q)
                    if self.check_collision_extend(nearNode, uniDir, d):
                        nearNode.parent = nnode - 1
                        nearNode.cost = scost

    def check_collision_extend(self, nearNode, uniDir, d):
        tmpNode = copy.deepcopy(nearNode)
        for i in range(int(d / self.checksize)):
            for j in range(self.DOF):
                tmpNode.q[j] += self.checksize * uniDir[j]
            if not self.__CollisionCheck(tmpNode):
                return False
        return True

    def cal_visibility(self, nearNode, uniDir, d):
        step = 0
        tmpNode = copy.deepcopy(nearNode)
        while self.__CollisionCheck(tmpNode):
            for j in range(self.DOF):
                tmpNode.q[j] += self.checksize * uniDir[j]
            step += 1
        step = step - 1
        return step

    def GetNearestListIndex(self, rndQ):
        dlist = []
        for node in self.nodeTree:
            dist = 0.0
            for i in range(self.DOF):
                dist += (node.q[i] - rndQ[i])**2
            dlist.append(dist)       
        minidx = dlist.index(min(dlist))
        return minidx
    
    def GetNearestNeighborDist(self, rndQ):
        dlist = []
        for node in self.failNodes:
            dist = 0.0
            for i in range(self.DOF):
                dist += (node.q[i] - rndQ[i])**2
            dlist.append(dist)
        mindist = min(dlist)
        return mindist
    
    def __CollisionCheck(self, node):
        self.robot.SetActiveDOFValues(node.q);
        #self.env.UpdatePublishedBodies();
        if self.env.CheckCollision(self.robot) or self.robot.CheckSelfCollision():
            return False
        else:
            return True
    def __CollisionCheckQ(self, Q):
        self.robot.SetActiveDOFValues(Q);
        #self.env.UpdatePublishedBodies();
        if self.env.CheckCollision(self.robot) or self.robot.CheckSelfCollision():
            return False
        else:
            return True


    def DrawGraph(self, rnd=None):
        plt.clf()
        if rnd is not None:
            plt.plot(rnd[0], rnd[1], "^k")
        
        for node in self.nodeTree:
            if node.parent is not None:
                plt.plot([node.q[0], self.nodeTree[node.parent].q[0]], [
                         node.q[1], self.nodeTree[node.parent].q[1]], "-b")
        
        for failNode in self.failNodes:
            plt.plot(failNode.q[0],failNode.q[1],'xr')
        plt.plot(self.start.q[0], self.start.q[1], "oy")
        plt.plot(self.goal.q[0], self.goal.q[1], "oy")
        plt.axis([-3.5, 0.1, -1.5, 1.5])
        plt.grid(True)
        plt.pause(0.01)