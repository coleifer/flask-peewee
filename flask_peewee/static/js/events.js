/*
SimplEE, A simple EventEmitter utility library for client-side use. Mimics
Node.js's EventEmitter object.

Author: Chris Dickinson
Source: https://github.com/chrisdickinson/simplee

Copyright (c) 2011, Chris Dickinson 
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of SimplEE nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

-- use --

var ajaxResult = function(endpoint, data) {
    var ee = new SimplEE.EventEmitter();
    $.ajax({
        'url':endpoint,
        'type':'POST',
        'data':data,
        'success':ee.emit.bind(ee, 'data'),
        'error':ee.emit.bind(ee, 'error')
    });

    return ee;
};

ajaxResult('/something/', {}).
    on('data', function() {
        // do something
    }).
    on('error', function() {
        // attempt to recover
    });


-- global events --

var Renderer = function() {

};

Renderer.prototype.renderSomething = SimplEE.emits('rendered', function(obj) {
    return [obj, "<div></div>"];
});

SimplEE.global.on('rendered', function(obj, html) {
    // do something
});

*/
var Events = (typeof window !== 'undefined') ?
  window.Events || {} :
  exports;

(function(exports) {
  var slice = Array.prototype.slice;

  var EventEmitter = function() {
    this._listeners = {};
  };

  EventEmitter.prototype.on = function(name, fn) {
    this._listeners[name] = this._listeners[name] || [];
    this._listeners[name].push(fn);
    return this;
  };

  EventEmitter.prototype.remove = function(name, fn) {
    fn && this._listeners[name] && this._listeners[name].splice(this._listeners[name].indexOf(fn), 1);
  };

  EventEmitter.prototype.emit = function(name) {

    var listeners = this._listeners[name] || [],
        args = slice.call(arguments, 1);
    for(var i = 0, len = listeners.length; i < len; ++i) {
      try {
        listeners[i].apply(this, args); 
      } catch(err) {
        this.emit('error', err);
      }
    }
  };

  EventEmitter.prototype.emits = function(name, fn) {
    var ee = this;
    return function() {
      var args = slice.call(arguments),
          result = fn.apply(this, args),
          emit = result instanceof Array ? result : [result];

      // destructuring emit
      ee.emit.apply(ee, [name].concat(emit));
      return result; 
    };
  };

  exports.EventEmitter = EventEmitter;
  exports.global = new EventEmitter();
  exports.emits = function() {
    return exports.global.emits.apply(exports.global, slice.call(arguments));
  };
})(Events);
