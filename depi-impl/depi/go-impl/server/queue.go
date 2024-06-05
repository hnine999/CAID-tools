package server

import (
	"errors"
	"sync"
)

type QueueItem[T any] struct {
	item T
	next *QueueItem[T]
}

type Queue[T any] struct {
	head        *QueueItem[T]
	tail        *QueueItem[T]
	lock        sync.Mutex
	closed      bool
	waiting     bool
	waitChannel chan bool
}

func NewQueue[T any]() *Queue[T] {
	return &Queue[T]{
		waitChannel: make(chan bool, 1),
	}
}

func (q *Queue[T]) IsEmpty() bool {
	q.lock.Lock()
	defer q.lock.Unlock()
	return q.head == nil
}

func (q *Queue[T]) Push(item T) {
	q.lock.Lock()

	if q.closed {
		q.lock.Unlock()
		return
	}

	qItem := &QueueItem[T]{
		item: item,
		next: nil,
	}
	if q.head == nil {
		q.head = qItem
		q.tail = qItem
		if q.waiting {
			q.waiting = false
			q.lock.Unlock()
			q.waitChannel <- true
			q.lock.Lock()
		}
	} else {
		q.tail.next = qItem
		q.tail = qItem
	}
	q.lock.Unlock()
}

func (q *Queue[T]) Pop() (T, error) {
	q.lock.Lock()
	defer q.lock.Unlock()

	if q.head == nil {
		var nothing T
		return nothing, errors.New("tried to pop from an empty queue")
	}

	if q.closed {
		var nothing T
		return nothing, errors.New("tried to pop from a closed queue")
	}
	returnItem := q.head
	q.head = q.head.next
	if q.head == nil {
		q.tail = nil
	}
	return returnItem.item, nil
}

func (q *Queue[T]) Close() {
	q.lock.Lock()
	defer q.lock.Unlock()

	q.closed = true
	if q.waiting {
		q.waiting = false
		q.waitChannel <- true
	}
}

func (q *Queue[T]) IsClosed() bool {
	q.lock.Lock()
	defer q.lock.Unlock()

	return q.closed
}

func (q *Queue[T]) PopWait() (T, error) {
	q.lock.Lock()

	if q.head == nil {
		q.waiting = true
		q.lock.Unlock()
		<-q.waitChannel
		q.lock.Lock()
	}
	q.lock.Unlock()
	return q.Pop()
}
