# Copyright 2016 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ------------------------------------------------------------------------------

from __future__ import print_function

import copy
import numpy


class AdjacencyMatrix(object):
    def __init__(self, n_mag, mat=None):
        self.__n_mag = int(n_mag)
        self.__mat = None
        if mat is not None:
            self.set_mat(mat)

    def get_mat(self):
        return copy.deepcopy(self.__mat)

    def get_val(self, row, col):
        assert self.__mat is not None
        return self.__mat[row][col]

    def set_mat(self, mat):
        if isinstance(mat, list):
            mat = numpy.array(mat)
        assert isinstance(mat, numpy.ndarray)
        assert (self.__n_mag, self.__n_mag) == mat.shape
        for row in mat:
            for col in row:
                assert col in [0, 1]
        self.__mat = mat.astype(int)

    def negate(self):
        ret = copy.deepcopy(self.__mat)
        if ret is not None:
            for i in range(self.__n_mag):
                for j in range(self.__n_mag):
                    ret[i][j] = (ret[i][j] + 1) % 2
        return ret

    def diagonal(self):
        return numpy.diagonal(self.__mat)

    def p_print(self):
        if self.__mat is not None:
            for row in self.__mat:
                for col in row:
                    print('{:3}'.format(col), end=' ')
                print()
        else:
            print(self.__mat)


class AdjacencyMatrixAnimation(object):
    def __init__(self, n_mag):
        self.__n_mag = n_mag
        self.__prv = None
        self.__cur = None

    def set_mat(self, mat):
        if self.__prv is None and self.__cur is None:
            zero_mat = numpy.zeros(shape=(self.__n_mag, self.__n_mag))
            self.__cur = AdjacencyMatrix(self.__n_mag, mat=zero_mat)
        self.__prv = self.__cur
        self.__cur = AdjacencyMatrix(self.__n_mag, mat=mat)

    def get_mat(self):
        return self.__cur.get_mat()

    def get_val(self, row, col):
        return self.__cur.get_val(row, col)

    def deltas(self):
        mat = []
        for i in range(self.__n_mag):
            row = []
            for j in range(self.__n_mag):
                val = None
                prv = self.__prv.get_val(i, j)
                cur = self.__cur.get_val(i, j)
                if prv == 0 and cur == 1:
                    val = True
                elif prv == 1 and cur == 0:
                    val = False
                row.append(val)
            mat.append(row)
        return numpy.array(mat).astype(object)


class AdjacencyMatrixAnimationController(object):
    '''abstract class'''
    def __init__(self, n, diagonal_only, default_value):
        self.__N = n
        self.__diagonal_only = diagonal_only
        self.__animation = AdjacencyMatrixAnimation(n)
        self.__buffer = AdjacencyMatrix(n)
        assert default_value in [0, 1]
        mat = numpy.zeros(shape=(n, n))
        if default_value == 1:
            mat = numpy.ones(shape=(n, n))
        self.__buffer.set_mat(mat)

    def activate_1d(self, idx, **kwargs):
        pass

    def deactivate_1d(self, idx, **kwargs):
        pass

    def activate_2d(self, row, col, **kwargs):
        pass

    def deactivate_2d(self, row, col, **kwargs):
        pass

    def commit(self, **kwargs):
        '''must be overridden in concrete classes'''
        pass

    def __animate_1d(self, mat, **kwargs):
        delta_list = numpy.diagonal(mat)
        for (idx, val) in enumerate(delta_list):
            if val is True:
                self.activate_1d(idx, **kwargs)
            elif val is False:
                self.deactivate_1d(idx, **kwargs)
        self.commit(**kwargs)

    def __animate_2d(self, delta_mat, **kwargs):
        for row in range(self.__N):
            for col in range(self.__N):
                if delta_mat[row][col] is True:
                    self.activate_2d(row, col, **kwargs)
                if delta_mat[row][col] is False:
                    self.deactivate_2d(row, col, **kwargs)
        self.commit(**kwargs)

    def animate(self, mat=None, **kwargs):
        mat = self.__buffer.get_mat() if mat is None else mat
        self.__animation.set_mat(mat)
        self.__buffer = AdjacencyMatrix(self.__N)
        self.__buffer.set_mat(self.__animation.get_mat())
        delta_mat = self.__animation.deltas()
        has_delta = False
        for row in delta_mat:
            for col in row:
                if col is not None:
                    has_delta = True
                    break
            if has_delta is True:
                break
        if has_delta is True and self.__diagonal_only is True:
            self.__animate_1d(delta_mat, **kwargs)
        elif has_delta is True:
            self.__animate_2d(delta_mat, **kwargs)

    def get_mag(self):
        return self.__N

    def get_val(self, row, col):
        return self.__animation.get_val(row, col)

    def set_val(self, row, col):
        mat = self.__buffer.get_mat()
        mat[row][col] = 1
        self.__buffer.set_mat(mat)

    def clr_val(self, row, col):
        mat = self.__buffer.get_mat()
        mat[row][col] = 0
        self.__buffer.set_mat(mat)

    def get_mat(self):
        return self.__animation.get_mat()


class NodeController(AdjacencyMatrixAnimationController):
    '''abstract class'''
    def __init__(self, n):
        super(NodeController, self).__init__(n, True, 0)

    def activate_1d(self, idx, **kwargs):
        return self.activate(idx, **kwargs)

    def deactivate_1d(self, idx, **kwargs):
        return self.deactivate(idx, **kwargs)

    def activate(self, idx, **kwargs):
        '''must be overridden in concrete classes'''
        pass

    def deactivate(self, idx, **kwargs):
        '''must be overridden in concrete classes'''
        pass

    def turn_on(self, node_idx, animate=True, **kwargs):
        self.set_val(node_idx, node_idx)
        if animate:
            self.animate(**kwargs)

    def turn_off(self, node_idx, animate=True, **kwargs):
        self.clr_val(node_idx, node_idx)
        if animate:
            self.animate(**kwargs)


class EdgeController(AdjacencyMatrixAnimationController):
    '''abstract class'''
    def __init__(self, n):
        super(EdgeController, self).__init__(n, False, 1)

    def activate_2d(self, row, col, **kwargs):
        return self.activate(row, col, **kwargs)

    def deactivate_2d(self, row, col, **kwargs):
        return self.deactivate(row, col, **kwargs)

    def activate(self, row, col, **kwargs):
        '''must be overridden in concrete classes'''
        pass

    def deactivate(self, row, col, **kwargs):
        '''must be overridden in concrete classes'''
        pass

    # convenience method (currently unreachable)
    # def connect(self, src_idx, dst_idx, animate=True, **kwargs):
    #     self.clr_val(src_idx, dst_idx)
    #     if animate:
    #         self.animate(**kwargs)

    # convenience method (currently unreachable)
    # def sever(self, src_idx, dst_idx, animate=True, **kwargs):
    #     self.set_val(src_idx, dst_idx)
    #     if animate:
    #         self.animate(**kwargs)


class NopEdgeController(EdgeController):
    def __init__(self, net_config):
        super(NopEdgeController, self).__init__(net_config.n_mag)

    def activate(self, row, col, **kwargs):
        pass

    def deactivate(self, row, col, **kwargs):
        pass

    def commit(self, **kwargs):
        pass

    def shutdown(self, **kwargs):
        pass
