# -*- coding: utf-8 -*-

'''
@author: hzw77, gjz5038

Deep reinforcement learning agent

'''

import numpy as np
from keras.layers import Input, Dense, Conv2D, Flatten, BatchNormalization, Activation, Multiply, Add
from keras.models import Model, model_from_json, load_model
from keras.optimizers import RMSprop
from keras.callbacks import EarlyStopping, TensorBoard
from keras.layers.merge import concatenate, add
import random
import os

from network_agent import NetworkAgent, conv2d_bn, Selector, State


MEMO = "Deeplight"


class DeeplightAgent(NetworkAgent):
    def __init__(self, num_phases, num_actions, path_set):
        super(DeeplightAgent, self).__init__(num_phases=num_phases, path_set=path_set)

        self.num_actions = num_actions

        self.q_network = self.build_network()
        self.save_model("init_model")
        self.update_outdated = 0

        self.q_network_bar = self.build_network_from_copy(self.q_network)
        self.q_bar_outdated = 0
        if not self.para_set.SEPARATE_MEMORY:
            self.memory = self.build_memory()
        else:
            self.memory = self.build_memory_separate()
        self.average_reward = None

    def reset_update_count(self):

        self.update_outdated = 0
        self.q_bar_outdated = 0

    def set_update_outdated(self):

        self.update_outdated = - 2*self.para_set.UPDATE_PERIOD
        self.q_bar_outdated = 2*self.para_set.UPDATE_Q_BAR_FREQ

    def convert_state_to_input(self, state):

        ''' convert a state struct to the format for neural network input'''

        return [getattr(state, feature_name)
                for feature_name in self.para_set.LIST_STATE_FEATURE]

    def build_network(self):
        # Initialize a Q network

        # initialize feature node
        dic_input_node = {}
        for feature_name in self.para_set.LIST_STATE_FEATURE:
            dic_input_node[feature_name] = Input(shape=getattr(State, "D_"+feature_name.upper()),
                                                 name="input_"+feature_name)

        # add cnn to image features
        dic_flatten_node = {}
        for feature_name in self.para_set.LIST_STATE_FEATURE:
            if len(getattr(State, "D_"+feature_name.upper())) > 1:
                dic_flatten_node[feature_name] = self._cnn_network_structure(dic_input_node[feature_name])
            else:
                dic_flatten_node[feature_name] = dic_input_node[feature_name]

        # concatenate features
        list_all_flatten_feature = []
        for feature_name in self.para_set.LIST_STATE_FEATURE:
            list_all_flatten_feature.append(dic_flatten_node[feature_name])
        all_flatten_feature = concatenate(list_all_flatten_feature, axis=1, name="all_flatten_feature")

        # shared dense layer
        shared_dense = self._shared_network_structure(all_flatten_feature, self.para_set.D_DENSE)

        # build phase selector layer
        if "cur_phase" in self.para_set.LIST_STATE_FEATURE and self.para_set.PHASE_SELECTOR:
            list_selected_q_values = []
            for phase in range(self.num_phases):
                locals()["q_values_{0}".format(phase)] = self._separate_network_structure(
                    shared_dense, self.para_set.D_DENSE, self.num_actions, memo=phase)
                locals()["selector_{0}".format(phase)] = Selector(
                    phase, name="selector_{0}".format(phase))(dic_input_node["cur_phase"])
                locals()["q_values_{0}_selected".format(phase)] = Multiply(name="multiply_{0}".format(phase))(
                    [locals()["q_values_{0}".format(phase)],
                     locals()["selector_{0}".format(phase)]]
                )
                list_selected_q_values.append(locals()["q_values_{0}_selected".format(phase)])
            q_values = Add()(list_selected_q_values)
        else:
            q_values = self._separate_network_structure(shared_dense, self.para_set.D_DENSE, self.num_actions)

        network = Model(inputs=[dic_input_node[feature_name] for feature_name in self.para_set.LIST_STATE_FEATURE],
                        outputs=q_values)
        network.compile(optimizer=RMSprop(lr=self.para_set.LEARNING_RATE),
                        loss="mean_squared_error")
        network.summary()

        return network

    def build_memory_separate(self):
        memory_list=[]
        for i in range(self.num_phases):
            memory_list.append([[] for j in range(self.num_actions)])
        return memory_list

    def remember(self, state, action, reward, next_state):
        if self.para_set.SEPARATE_MEMORY:
            ''' log the history separately '''
            self.memory[state.cur_phase[0][0]][action].append([state, action, reward, next_state])
        else:
            self.memory.append([state, action, reward, next_state])

    def forget(self, is_pretrain):

        if self.para_set.SEPARATE_MEMORY:
            ''' remove the old history if the memory is too large, in a separate way '''
            for phase_i in range(self.num_phases):
                for action_i in range(self.num_actions):
                    if is_pretrain:
                        random.shuffle(self.memory[phase_i][action_i])
                    if len(self.memory[phase_i][action_i]) > self.para_set.MAX_MEMORY_LEN:
                        print("length of memory (state {0}, action {1}): {2}, before forget".format(
                            phase_i, action_i, len(self.memory[phase_i][action_i])))
                        self.memory[phase_i][action_i] = self.memory[phase_i][action_i][-self.para_set.MAX_MEMORY_LEN:]
                    print("length of memory (state {0}, action {1}): {2}, after forget".format(
                        phase_i, action_i, len(self.memory[phase_i][action_i])))
        else:
            if len(self.memory) > self.para_set.MAX_MEMORY_LEN:
                print("length of memory: {0}, before forget".format(len(self.memory)))
                self.memory = self.memory[-self.para_set.MAX_MEMORY_LEN:]
            print("length of memory: {0}, after forget".format(len(self.memory)))

    def _cal_average(self, sample_memory):

        list_reward = []
        average_reward = np.zeros((self.num_phases, self.num_actions))
        for phase_i in range(self.num_phases):
            list_reward.append([])
            for action_i in range(self.num_actions):
                list_reward[phase_i].append([])
        for [state, action, reward, _] in sample_memory:
            phase = state.cur_phase[0][0]
            list_reward[phase][action].append(reward)

        for phase_i in range(self.num_phases):
            for action_i in range(self.num_actions):
                if len(list_reward[phase_i][action_i]) != 0:
                    average_reward[phase_i][action_i] = np.average(list_reward[phase_i][action_i])

        return average_reward

    def _cal_average_separate(self, sample_memory):
        # Calculate average rewards for different cases
        average_reward = np.zeros((self.num_phases, self.num_actions))

        for phase_i in range(self.num_phases):
            for action_i in range(self.num_actions):
                len_sample_memory = len(sample_memory[phase_i][action_i])

                if len_sample_memory > 0:
                    list_reward = []

                    for i in range(len_sample_memory):
                        state, action, reward, _ = sample_memory[phase_i][action_i][i]
                        list_reward.append(reward)

                    average_reward[phase_i][action_i] = np.average(list_reward)

        return average_reward

    def get_sample(self, memory_slice, dic_state_feature_arrays, Y, gamma, prefix, use_average):
        len_memory_slice = len(memory_slice)

        f_samples = open(os.path.join(self.path_set.PATH_TO_OUTPUT, "{0}_memory".format(prefix)), "a")

        for i in range(len_memory_slice):
            state, action, reward, next_state = memory_slice[i]
            for feature_name in self.para_set.LIST_STATE_FEATURE:
                dic_state_feature_arrays[feature_name].append(getattr(state, feature_name)[0])

            if state.if_terminal:
                next_estimated_reward = 0
            else:
                next_estimated_reward = self._get_next_estimated_reward(next_state)

            total_reward = reward + gamma * next_estimated_reward

            if not use_average:
                target = self.q_network.predict(
                    self.convert_state_to_input(state))
            else:
                target = np.copy(np.array([self.average_reward[state.cur_phase[0][0]]]))

            pre_target = np.copy(target)
            target[0][action] = total_reward
            Y.append(target[0])

            for feature_name in self.para_set.LIST_STATE_FEATURE:
                if "map" not in feature_name:
                    f_samples.write("{0}\t".format(str(getattr(state, feature_name))))
            f_samples.write("{0}\t{1}\t{2}\t{3}\t{4}\n".format(str(pre_target), str(target), str(action), str(reward), str(next_estimated_reward)))

        f_samples.close()

        return dic_state_feature_arrays, Y

    def train_network(self, Xs, Y, prefix, is_pretrain):
        if is_pretrain:
            epochs = self.para_set.EPOCHS_PRETRAIN
        else:
            epochs = self.para_set.EPOCHS
        batch_size = min(self.para_set.BATCH_SIZE, len(Y))

        early_stopping = EarlyStopping(
            monitor='val_loss', patience=self.para_set.PATIENCE, verbose=0, mode='min')

        hist = self.q_network.fit(Xs, Y, batch_size=batch_size, epochs=epochs,
                                  shuffle=False, verbose=2,
                                  validation_split=0.3, callbacks=[early_stopping])
        self.save_model(prefix)

    def update_network(self, is_pretrain, use_average, current_time):
        # If the UPDATE_PERIOD time already passed it executes
        if current_time - self.update_outdated >= self.para_set.UPDATE_PERIOD:
            self.update_outdated = current_time
        else:
            return

        # Selects gamma
        gamma = self.para_set.GAMMA_PRETRAIN if is_pretrain else self.para_set.GAMMA

        # Initializes an empty dict with the features as keys
        dic_state_feature_arrays = {}
        for feature_name in self.para_set.LIST_STATE_FEATURE:
            dic_state_feature_arrays[feature_name] = []
        Y = []

        # Gets average for each state-action pair reward (4x4 float matrix)
        if self.para_set.SEPARATE_MEMORY:
            self.average_reward = self._cal_average_separate(self.memory)
        else:
            self.average_reward = self._cal_average(self.memory)

        # Gets a limited sample of each state-action pair
        if self.para_set.SEPARATE_MEMORY:
            for phase_i in range(self.num_phases):
                for action_i in range(self.num_actions):
                    sampled_memory = self._sample_memory(
                        gamma=gamma,
                        with_priority=self.para_set.PRIORITY_SAMPLING,
                        memory=self.memory[phase_i][action_i],
                        is_pretrain=is_pretrain)
                    # Appends these samples features to the dict and q-values to Y
                    dic_state_feature_arrays, Y = self.get_sample(
                        sampled_memory, dic_state_feature_arrays, Y, gamma, current_time, use_average)
        else:
            sampled_memory = self._sample_memory(
                gamma=gamma,
                with_priority=self.para_set.PRIORITY_SAMPLING,
                memory=self.memory,
                is_pretrain=is_pretrain)
            dic_state_feature_arrays, Y = self.get_sample(
                sampled_memory, dic_state_feature_arrays, Y, gamma, current_time, use_average)

        # Organizes the data array to better feed it the network
        Xs = [np.array(dic_state_feature_arrays[feature_name]) for feature_name in self.para_set.LIST_STATE_FEATURE]
        Y = np.array(Y)
        sample_weight = np.ones(len(Y))
        # Shuffle the training samples, especially for different phases and actions
        Xs, Y, _ = self._unison_shuffled_copies(Xs, Y, sample_weight)

        # Training
        self.train_network(Xs, Y, current_time, is_pretrain)
        self.q_bar_outdated += 1
        self.forget(is_pretrain=is_pretrain)

    def _sample_memory(self, gamma, with_priority, memory, is_pretrain):

        len_memory = len(memory)

        if not is_pretrain:
            sample_size = min(self.para_set.SAMPLE_SIZE, len_memory)
        else:
            sample_size = min(self.para_set.SAMPLE_SIZE_PRETRAIN, len_memory)

        if with_priority:
            # sample with priority
            sample_weight = []
            for i in range(len_memory):
                state, action, reward, next_state = memory[i]

                if state.if_terminal:
                    next_estimated_reward = 0
                else:
                    next_estimated_reward = self._get_next_estimated_reward(next_state)

                total_reward = reward + gamma * next_estimated_reward
                target = self.q_network.predict(
                    self.convert_state_to_input(state))
                pre_target = np.copy(target)
                target[0][action] = total_reward

                # get the bias of current prediction
                weight = abs(pre_target[0][action] - total_reward)
                sample_weight.append(weight)

            priority = self._cal_priority(sample_weight)
            p = random.choices(range(len(priority)), weights=priority, k=sample_size)
            sampled_memory = np.array(memory)[p]
        else:
            sampled_memory = random.sample(memory, sample_size)

        return sampled_memory

    @staticmethod
    def _cal_priority(sample_weight):
        pos_constant = 0.0001
        alpha = 1
        sample_weight_np = np.array(sample_weight)
        sample_weight_np = np.power(sample_weight_np + pos_constant, alpha) / sample_weight_np.sum()
        return sample_weight_np
