/**
 * 统一 HTML/JSON 解析器
 * 结合轻量级HTML解析器(lite)和完整HTML解析器(cheerio版本)
 * 不依赖 cheerio，使用纯正则表达式实现，同时支持JSONPath解析
 * 
 * 支持的选择器语法：
 * - 标签名: div, p, a, img
 * - 类选择器: .class-name
 * - ID选择器: #id-name
 * - 属性选择器: [attr], [attr=value]
 * - 组合选择器: div.class, div#id, img:last-of-type
 * - 后代选择器: div p (空格分隔)
 * - 伪选择器: :eq(n), :first, :last, :eq(-1), :last-of-type, :first-of-type
 * - :has(selector) - 匹配包含指定子元素的元素
 * - :contains(text) - 匹配包含指定文本的元素
 * - 排除语法: p--a (获取p标签内容但排除a标签)
 * - 海阔视界语法: && 分隔, Text, Html
 */

(function(global) {
  'use strict';

  // ============================================
  // 常量定义
  // ============================================
  var URLJOIN_ATTR = /(url|src|href|-original|-src|-play|-url|style)$|^(data-|url-|src-)/;
  var SPECIAL_URL = /^(ftp|magnet|thunder|ws):/;
  var SELF_CLOSING_TAGS = /^(img|br|hr|input|meta|link|area|base|col|embed|param|source|track|wbr)$/i;
  
  // 解析缓存开关
  var PARSE_CACHE = true;
  // 不自动加eq下标索引的选择器
  var NOADD_INDEX = ':eq|:lt|:gt|:first|:last|:not|:even|:odd|:has|:contains|:matches|:empty|^body$|^#';

  // ============================================
  // HTML 元素类
  // ============================================
  function HtmlElement(tagName, attributes, innerHTML, outerHTML) {
    this.tagName = (tagName || '').toLowerCase();
    this.attributes = attributes || {};
    this.innerHTML = innerHTML || '';
    this.outerHTML = outerHTML || '';
  }

  HtmlElement.prototype.attr = function(name) {
    if (!name) return '';
    var lowerName = name.toLowerCase();
    return this.attributes[name] || this.attributes[lowerName] || '';
  };

  HtmlElement.prototype.text = function() {
    return this.innerHTML
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&amp;/g, '&')
      .replace(/&quot;/g, '"')
      .replace(/&#(\d+);/g, function(m, c) { return String.fromCharCode(c); })
      .replace(/\s+/g, ' ')
      .trim();
  };

  HtmlElement.prototype.html = function() {
    return this.innerHTML;
  };

  // ============================================
  // 工具函数
  // ============================================
  
  /**
   * 解析 HTML 标签的属性
   */
  function parseAttributes(attrString) {
    var attrs = {};
    if (!attrString) return attrs;
    
    var attrRegex = /([\w-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
    var match;
    
    while ((match = attrRegex.exec(attrString)) !== null) {
      var name = match[1].toLowerCase();
      var value = match[2] !== undefined ? match[2] : 
                  match[3] !== undefined ? match[3] : 
                  match[4] !== undefined ? match[4] : '';
      attrs[name] = value;
    }
    
    return attrs;
  }

  /**
   * URL 拼接
   */
  function urlJoin(base, path) {
    if (!path) return base || '';
    if (!base) return path;
    if (/^https?:\/\//i.test(path)) return path;
    if (path.indexOf('//') === 0) {
      return (base.indexOf('https://') === 0 ? 'https:' : 'http:') + path;
    }
    if (path.indexOf('/') === 0) {
      var m = base.match(/^(https?:\/\/[^\/]+)/i);
      return m ? m[1] + path : path;
    }
    
    var baseUrl = base.split('?')[0];
    if (baseUrl.charAt(baseUrl.length - 1) !== '/') {
      var idx = baseUrl.lastIndexOf('/');
      baseUrl = idx > 8 ? baseUrl.substring(0, idx + 1) : baseUrl + '/';
    }
    
    while (path.indexOf('../') === 0) {
      path = path.substring(3);
      var idx2 = baseUrl.lastIndexOf('/', baseUrl.length - 2);
      if (idx2 > 8) baseUrl = baseUrl.substring(0, idx2 + 1);
    }
    
    if (path.indexOf('./') === 0) path = path.substring(2);
    return baseUrl + path;
  }

  /**
   * 清理文本
   */
  function cleanText(text) {
    if (!text) return '';
    return text.replace(/[\s]+/g, ' ').trim();
  }

  /**
   * 正则测试
   */
  function regexTest(pattern, text) {
    if (!pattern || !text) return false;
    var regex = new RegExp(pattern, 'i');
    return regex.test(text);
  }

  /**
   * 检查字符串是否包含指定内容
   */
  function contains(text, match) {
    return text && text.indexOf(match) !== -1;
  }

  // ============================================
  // 选择器解析
  // ============================================
  
  /**
   * 解析选择器，提取标签名、类名、ID、属性和伪选择器
   */
  function parseSelector(selector) {
    var result = {
      tagName: null,
      classNames: [],
      idName: null,
      attrs: {},
      pseudo: null,
      pseudoArg: null,
      hasSelector: null
    };
    
    if (!selector) return result;
    selector = selector.trim();
    
    // 解析 :has() 伪选择器
    var hasMatch = selector.match(/:has\(([^)]+)\)/);
    if (hasMatch) {
      result.hasSelector = hasMatch[1].trim();
      selector = selector.replace(/:has\([^)]+\)/, '');
    }
    
    // 解析 :contains() 伪选择器
    var containsMatch = selector.match(/:contains\(([^)]+)\)/);
    if (containsMatch) {
      result.pseudo = 'contains';
      result.pseudoArg = containsMatch[1].replace(/^['"]|['"]$/g, '');
      selector = selector.replace(/:contains\([^)]+\)/, '');
    }
    
    // 解析伪选择器
    var pseudoMatch = selector.match(/:(\w+(?:-\w+)*)(?:\((-?\d+)\))?$/);
    if (pseudoMatch && !result.pseudo) {
      result.pseudo = pseudoMatch[1];
      result.pseudoArg = pseudoMatch[2] !== undefined ? parseInt(pseudoMatch[2]) : null;
      selector = selector.replace(/:[\w-]+(?:\(-?\d+\))?$/, '');
    }
    
    // 解析属性选择器
    var attrRegex = /\[([\w-]+)(?:([*^$~]?)=["']?([^"'\]]+)["']?)?\]/g;
    var attrMatch;
    while ((attrMatch = attrRegex.exec(selector)) !== null) {
      var attrName = attrMatch[1].toLowerCase();
      var matchMode = attrMatch[2] || '';
      var attrValue = attrMatch[3];
      
      if (attrValue === undefined) {
        result.attrs[attrName] = { mode: 'exists', value: true };
      } else {
        result.attrs[attrName] = { mode: matchMode || 'exact', value: attrValue };
      }
    }
    selector = selector.replace(/\[[\w-]+(?:[*^$~]?=["']?[^"'\]]+["']?)?\]/g, '');
    
    // 解析 #id
    var idMatch = selector.match(/#([\w-]+)/);
    if (idMatch) {
      result.idName = idMatch[1];
      selector = selector.replace(/#[\w-]+/, '');
    }
    
    // 解析 .class
    var classRegex = /\.([\w-]+)/g;
    var classMatch;
    while ((classMatch = classRegex.exec(selector)) !== null) {
      result.classNames.push(classMatch[1]);
    }
    selector = selector.replace(/\.[\w-]+/g, '');
    
    // 剩余的是标签名
    selector = selector.trim();
    if (selector && selector !== '*') {
      result.tagName = selector.toLowerCase();
    }
    
    return result;
  }

  /**
   * 检查元素是否匹配选择器条件
   */
  function matchesSelector(element, selectorInfo) {
    if (selectorInfo.tagName && element.tagName !== selectorInfo.tagName) return false;
    if (selectorInfo.idName && element.attributes.id !== selectorInfo.idName) return false;
    
    if (selectorInfo.classNames.length > 0) {
      var elementClasses = (element.attributes.class || '').split(/\s+/);
      for (var i = 0; i < selectorInfo.classNames.length; i++) {
        if (elementClasses.indexOf(selectorInfo.classNames[i]) === -1) return false;
      }
    }
    
    for (var attrKey in selectorInfo.attrs) {
      var attrVal = element.attributes[attrKey];
      var attrRule = selectorInfo.attrs[attrKey];
      
      if (typeof attrRule !== 'object') {
        attrRule = { mode: attrRule === true ? 'exists' : 'exact', value: attrRule };
      }
      
      if (attrVal === undefined) return false;
      
      switch (attrRule.mode) {
        case 'exists': break;
        case 'exact': case '': if (attrVal !== attrRule.value) return false; break;
        case '*': if (attrVal.indexOf(attrRule.value) === -1) return false; break;
        case '^': if (attrVal.indexOf(attrRule.value) !== 0) return false; break;
        case '$': if (attrVal.indexOf(attrRule.value) !== attrVal.length - attrRule.value.length) return false; break;
        case '~':
          var words = attrVal.split(/\s+/);
          if (words.indexOf(attrRule.value) === -1) return false;
          break;
        default: if (attrVal !== attrRule.value) return false;
      }
    }
    
    if (selectorInfo.hasSelector) {
      var innerHtml = element.innerHTML || element.outerHTML;
      var hasElements = findElements(innerHtml, selectorInfo.hasSelector);
      if (hasElements.length === 0) return false;
    }
    
    if (selectorInfo.pseudo === 'contains' && selectorInfo.pseudoArg) {
      var text = element.text ? element.text() : '';
      if (text.indexOf(selectorInfo.pseudoArg) === -1) return false;
    }
    
    return true;
  }

  /**
   * 应用伪选择器过滤
   */
  function applyPseudo(elements, pseudo, pseudoArg) {
    if (!pseudo || elements.length === 0) return elements;
    
    switch (pseudo) {
      case 'eq':
        if (pseudoArg !== null) {
          var idx = pseudoArg < 0 ? elements.length + pseudoArg : pseudoArg;
          return (idx >= 0 && idx < elements.length) ? [elements[idx]] : [];
        }
        return elements;
      case 'first': return elements.length > 0 ? [elements[0]] : [];
      case 'last': return elements.length > 0 ? [elements[elements.length - 1]] : [];
      case 'first-of-type': return elements.length > 0 ? [elements[0]] : [];
      case 'last-of-type': return elements.length > 0 ? [elements[elements.length - 1]] : [];
      case 'lt': return pseudoArg !== null ? elements.slice(0, pseudoArg) : elements;
      case 'gt': return pseudoArg !== null ? elements.slice(pseudoArg + 1) : elements;
      case 'even': return elements.filter(function(_, i) { return i % 2 === 0; });
      case 'odd': return elements.filter(function(_, i) { return i % 2 === 1; });
      default: return elements;
    }
  }

  /**
   * 在 HTML 中查找所有匹配的元素
   */
  function findElements(html, selector) {
    if (!html || !selector) return [];
    
    var selectorInfo = parseSelector(selector);
    var results = [];
    
    var tagToFind = selectorInfo.tagName || '[a-zA-Z][a-zA-Z0-9]*';
    var openTagRegex = new RegExp('<(' + tagToFind + ')(\\s[^>]*)?>|<(' + tagToFind + ')(\\s[^>]*)?/>', 'gi');
    var match;
    
    while ((match = openTagRegex.exec(html)) !== null) {
      var matchedTag = (match[1] || match[3] || '').toLowerCase();
      var attrString = match[2] || match[4] || '';
      var startPos = match.index;
      var isSelfClosing = match[0].endsWith('/>') || SELF_CLOSING_TAGS.test(matchedTag);
      
      var parsedAttrs = parseAttributes(attrString);
      var element = new HtmlElement(matchedTag, parsedAttrs, '', match[0]);
      
      if (!matchesSelector(element, selectorInfo)) continue;
      
      if (!isSelfClosing) {
        var depth = 1;
        var searchPos = startPos + match[0].length;
        var contentStart = searchPos;
        
        var closeTagRegex = new RegExp('<(/?)(' + matchedTag + ')(\\s[^>]*)?>|<' + matchedTag + '(\\s[^>]*)?/>', 'gi');
        closeTagRegex.lastIndex = searchPos;
        
        var tagMatch;
        while ((tagMatch = closeTagRegex.exec(html)) !== null) {
          if (tagMatch[0].endsWith('/>')) continue;
          if (tagMatch[1] === '/') {
            depth--;
            if (depth === 0) {
              element.innerHTML = html.substring(contentStart, tagMatch.index);
              element.outerHTML = html.substring(startPos, tagMatch.index + tagMatch[0].length);
              break;
            }
          } else if (tagMatch[2]) {
            depth++;
          }
        }
      }
      
      results.push(element);
    }
    
    return applyPseudo(results, selectorInfo.pseudo, selectorInfo.pseudoArg);
  }

  // ============================================
  // 海阔视界语法转换
  // ============================================
  
  /**
   * 将海阔视界解析语法转换为选择器
   */
  function parseHikerToJq(parse, first) {
    if (!parse) return parse;
    
    if (contains(parse, '&&')) {
      var parses = parse.split('&&');
      var newParses = [];
      for (var i = 0; i < parses.length; i++) {
        var psList = parses[i].split(' ');
        var ps = psList[psList.length - 1];
        if (!regexTest(NOADD_INDEX, ps)) {
          if (!first && i >= parses.length - 1) {
            newParses.push(parses[i]);
          } else {
            newParses.push(parses[i] + ':eq(0)');
          }
        } else {
          newParses.push(parses[i]);
        }
      }
      parse = newParses.join(' ');
    } else {
      var psList = parse.split(' ');
      var ps = psList[psList.length - 1];
      if (!regexTest(NOADD_INDEX, ps) && first) {
        parse = parse + ':eq(0)';
      }
    }
    return parse;
  }

  /**
   * 获取解析信息
   */
  function getParseInfo(nparse) {
    var excludes = [];
    var nparseIndex = 0;
    var nparseRule = nparse;
    
    if (contains(nparse, ':eq')) {
      nparseRule = nparse.split(':eq')[0];
      var nparsePos = nparse.split(':eq')[1];
      if (contains(nparseRule, '--')) {
        excludes = nparseRule.split('--').slice(1);
        nparseRule = nparseRule.split('--')[0];
      } else if (contains(nparsePos, '--')) {
        excludes = nparsePos.split('--').slice(1);
        nparsePos = nparsePos.split('--')[0];
      }
      try {
        nparseIndex = parseInt(nparsePos.split('(')[1].split(')')[0]);
      } catch(e) {}
    } else if (contains(nparse, '--')) {
      nparseRule = nparse.split('--')[0];
      excludes = nparse.split('--').slice(1);
    }
    
    return { nparseRule: nparseRule, nparseIndex: nparseIndex, excludes: excludes };
  }

  /**
   * 重排相邻的 :gt 和 :lt 选择器
   */
  function reorderAdjacentLtAndGt(selector) {
    var adjacentPattern = /:gt\((\d+)\):lt\((\d+)\)/;
    var match;
    while ((match = adjacentPattern.exec(selector)) !== null) {
      var replacement = ':lt(' + match[2] + '):gt(' + match[1] + ')';
      selector = selector.substring(0, match.index) + replacement + selector.substring(match.index + match[0].length);
      adjacentPattern.lastIndex = match.index;
    }
    return selector;
  }

  /**
   * 解析单个规则
   */
  function parseOneRule(doc, nparse, ret, findElementsFn) {
    var info = getParseInfo(nparse);
    var nparseRule = reorderAdjacentLtAndGt(info.nparseRule);
    
    if (!ret) {
      ret = findElementsFn(doc, nparseRule);
    } else {
      // 在已有元素中查找
      var newRet = [];
      for (var i = 0; i < ret.length; i++) {
        var innerElements = findElementsFn(ret[i].innerHTML, nparseRule);
        newRet = newRet.concat(innerElements);
      }
      ret = newRet;
    }
    
    if (contains(nparse, ':eq') && ret && ret.length > info.nparseIndex) {
      ret = [ret[info.nparseIndex]];
    }
    
    if (info.excludes.length > 0 && ret && ret.length > 0) {
      // 排除指定标签
      var newRet = [];
      for (var j = 0; j < ret.length; j++) {
        var html = ret[j].innerHTML;
        for (var k = 0; k < info.excludes.length; k++) {
          var excludeRegex = new RegExp('<' + info.excludes[k] + '[^>]*>[\\s\\S]*?</' + info.excludes[k] + '>', 'gi');
          html = html.replace(excludeRegex, '');
          var selfCloseRegex = new RegExp('<' + info.excludes[k] + '[^>]*/>', 'gi');
          html = html.replace(selfCloseRegex, '');
        }
        var newElement = new HtmlElement(ret[j].tagName, ret[j].attributes, html, '');
        newRet.push(newElement);
      }
      ret = newRet;
    }
    
    return ret || [];
  }

  // ============================================
  // JSONPath 支持
  // ============================================
  
  /**
   * JSONPath 查询
   */
  var jsonpath = {
    query: function(jsonObject, path) {
      if (typeof JSONPath !== 'undefined' && JSONPath.JSONPath) {
        return JSONPath.JSONPath({ path: path, json: jsonObject });
      }
      // 简易 JSONPath 实现（仅支持基础语法）
      try {
        if (!path.startsWith('$.')) path = '$.' + path;
        var keys = path.replace(/^\$\./, '').split('.');
        var result = jsonObject;
        for (var i = 0; i < keys.length; i++) {
          var key = keys[i];
          if (key === '*') {
            if (Array.isArray(result)) return result;
            return [];
          }
          if (key.includes('[')) {
            var bracketMatch = key.match(/([^\[]+)?\[(\d+)\]/);
            if (bracketMatch) {
              var arrKey = bracketMatch[1];
              var idx = parseInt(bracketMatch[2]);
              if (arrKey) result = result[arrKey];
              result = Array.isArray(result) && result[idx] ? result[idx] : undefined;
            }
          } else {
            result = result ? result[key] : undefined;
          }
          if (result === undefined) return [];
        }
        return result !== undefined ? [result] : [];
      } catch(e) {
        return [];
      }
    }
  };

  // ============================================
  // 导出 API
  // ============================================
  
  /**
   * load - cheerio 兼容接口
   */
  function load(html) {
    if (!html) html = '';
    
    function createEmpty() {
      return {
        each: function() {},
        find: function() { return createEmpty(); },
        attr: function() { return ''; },
        text: function() { return ''; },
        html: function() { return ''; },
        toArray: function() { return []; }
      };
    }
    
    function wrapElement(el) {
      if (!el) return createEmpty();
      return {
        find: function(selector) {
          var inner = findElements(el.innerHTML || el.outerHTML || '', selector);
          return inner.length > 0 ? wrapElement(inner[0]) : createEmpty();
        },
        attr: function(name) {
          return (el.attr && el.attr(name)) || (el.attributes && (el.attributes[name] || el.attributes[name.toLowerCase()])) || '';
        },
        text: function() {
          var t = (el.text && el.text()) || '';
          return typeof t === 'string' ? t.trim() : '';
        },
        html: function() {
          return (el.innerHTML || '');
        },
        toArray: function() {
          return [el];
        }
      };
    }
    
    function query(sel) {
      if (typeof sel === 'string') {
        var elements = findElements(html, sel);
        return {
          each: function(cb) {
            for (var i = 0; i < elements.length; i++) {
              cb(i, elements[i]);
            }
          },
          find: function(selector) {
            var first = elements[0];
            return first ? wrapElement(first).find(selector) : createEmpty();
          },
          attr: function(name) {
            var first = elements[0];
            return first ? wrapElement(first).attr(name) : '';
          },
          text: function() {
            var first = elements[0];
            return first ? wrapElement(first).text() : '';
          },
          html: function() {
            var first = elements[0];
            return first ? (first.innerHTML || '') : '';
          },
          toArray: function() {
            return elements;
          }
        };
      }
      if (sel && (sel.innerHTML !== undefined || sel.outerHTML !== undefined)) {
        return wrapElement(sel);
      }
      return createEmpty();
    }
    
    query.html = function() { return html; };
    query.text = function() { return cleanText(html.replace(/<[^>]+>/g, ' ')); };
    
    return query;
  }

  /**
   * pdfa - 解析 HTML 返回匹配选择器的所有元素数组
   */
  function pdfa(html, parse) {
    if (!html || !parse) return [];
    
    try {
      parse = parseHikerToJq(parse, false);
      var parts = parse.split(' ');
      var currentElements = [html];
      
      for (var i = 0; i < parts.length; i++) {
        var selector = parts[i];
        var newElements = [];
        
        for (var j = 0; j < currentElements.length; j++) {
          var elements;
          if (typeof currentElements[j] === 'string') {
            elements = findElements(currentElements[j], selector);
          } else if (currentElements[j].innerHTML !== undefined) {
            elements = findElements(currentElements[j].innerHTML, selector);
          } else {
            elements = findElements(currentElements[j], selector);
          }
          newElements = newElements.concat(elements);
        }
        
        currentElements = newElements;
        if (currentElements.length === 0) break;
      }
      
      return currentElements.map(function(el) {
        return el.outerHTML;
      });
    } catch (e) {
      console.log('[pdfa] 异常: ' + e.message);
      return [];
    }
  }

  /**
   * pdfh - 解析 HTML 返回匹配选择器的第一个元素的文本/属性
   */
  function pdfh(html, parse, baseUrl) {
    if (!html || !parse) return '';
    
    try {
      if (parse === 'body&&Text' || parse === 'Text') {
        var tempEl = new HtmlElement('body', {}, html, html);
        return cleanText(tempEl.text());
      }
      if (parse === 'body&&Html' || parse === 'Html') {
        return html;
      }
      
      var parts = parse.split('&&');
      var option = null;
      var excludeTag = null;
      var selectors = [];
      
      for (var i = 0; i < parts.length; i++) {
        var part = parts[i].trim();
        if (!part) continue;
        if (part.toLowerCase() === 'body') continue;
        
        if (part.indexOf('--') > -1) {
          var excludeParts = part.split('--');
          part = excludeParts[0];
          excludeTag = excludeParts[1];
        }
        
        if (i === parts.length - 1) {
          var isAttr = (part === 'Text' || part === 'text' || 
                        part === 'Html' || part === 'html' ||
                        /^[\w-]+(\|\|[\w-]+)*$/.test(part));
          var commonTags = /^(div|span|p|a|img|ul|li|ol|h[1-6]|table|tr|td|th|tbody|thead|tfoot|body|head|html|section|article|nav|aside|header|footer|main|form|input|button|select|option|textarea|label|dl|dt|dd|figure|figcaption|video|audio|source|canvas|svg|iframe|script|style|link|meta|br|hr)$/i;
          
          if (isAttr && !commonTags.test(part.split('||')[0].split(':')[0])) {
            option = part;
            continue;
          }
        }
        
        var subParts = part.split(/\s+/);
        for (var j = 0; j < subParts.length; j++) {
          if (subParts[j]) selectors.push(subParts[j]);
        }
      }
      
      var currentHtml = html;
      var element = null;
      
      for (var k = 0; k < selectors.length; k++) {
        var elements = findElements(currentHtml, selectors[k]);
        if (elements.length === 0) return '';
        element = elements[0];
        currentHtml = element.innerHTML;
      }
      
      if (!element) return '';
      
      var processedHtml = element.innerHTML;
      if (excludeTag) {
        var excludeRegex = new RegExp('<' + excludeTag + '[^>]*>[\\s\\S]*?</' + excludeTag + '>', 'gi');
        processedHtml = processedHtml.replace(excludeRegex, '');
        var selfCloseRegex = new RegExp('<' + excludeTag + '[^>]*/>', 'gi');
        processedHtml = processedHtml.replace(selfCloseRegex, '');
      }
      
      if (option) {
        if (option === 'Text' || option === 'text') {
          var tempElement = new HtmlElement(element.tagName, element.attributes, processedHtml, '');
          return cleanText(tempElement.text());
        }
        if (option === 'Html' || option === 'html') {
          return processedHtml;
        }
        
        var attrOptions = option.split('||');
        var attrVal = '';
        
        for (var m = 0; m < attrOptions.length; m++) {
          var opt = attrOptions[m].trim();
          attrVal = element.attr(opt);
          
          if (/style/i.test(opt) && attrVal && attrVal.indexOf('url(') > -1) {
            var urlMatch = attrVal.match(/url\((['"]?)([^)]+)\1\)/);
            if (urlMatch) attrVal = urlMatch[2];
          }
          
          if (attrVal && baseUrl && regexTest(URLJOIN_ATTR.source, opt) && !regexTest(SPECIAL_URL.source, attrVal)) {
            attrVal = attrVal.indexOf('http') > -1 ? 
                      attrVal.slice(attrVal.indexOf('http')) : 
                      urlJoin(baseUrl, attrVal);
          }
          
          if (attrVal) break;
        }
        
        return attrVal;
      }
      
      return element.innerHTML;
    } catch (e) {
      console.log('[pdfh] 异常: ' + e.message);
      return '';
    }
  }

  /**
   * pd - 增强版的 pdfh，自动处理URL拼接并解码HTML实体
   */
  function pd(html, parse, baseUrl) {
    if (!baseUrl) {
      baseUrl = (typeof MY_URL !== 'undefined' && MY_URL) ? MY_URL : 
                (typeof HOST !== 'undefined' && HOST) ? HOST : '';
    }
    
    var result = pdfh(html, parse, baseUrl);
    
    if (result) {
      result = result.replace(/&amp;/g, '&')
                     .replace(/&lt;/g, '<')
                     .replace(/&gt;/g, '>')
                     .replace(/&quot;/g, '"')
                     .replace(/&#39;/g, "'")
                     .replace(/&#(\d+);/g, function(match, dec) {
                       return String.fromCharCode(dec);
                     });
    }
    
    if (!result && parse && parse.includes('&&')) {
      var parts = parse.split('&&');
      var lastPart = parts[parts.length - 1];
      
      if (/data-original|data-src|src|original/.test(lastPart)) {
        var possibleAttrs = ['data-original', 'data-src', 'src', 'original'];
        for (var i = 0; i < possibleAttrs.length; i++) {
          var attr = possibleAttrs[i];
          var newParse = parts.slice(0, -1).concat(attr).join('&&');
          var tempResult = pdfh(html, newParse, baseUrl);
          if (tempResult) {
            tempResult = tempResult.replace(/&amp;/g, '&')
                                   .replace(/&lt;/g, '<')
                                   .replace(/&gt;/g, '>')
                                   .replace(/&quot;/g, '"')
                                   .replace(/&#39;/g, "'")
                                   .replace(/&#(\d+);/g, function(match, dec) {
                                     return String.fromCharCode(dec);
                                   });
            result = tempResult;
            break;
          }
        }
      }
    }
    
    if (result && baseUrl && regexTest(URLJOIN_ATTR.source, parse) && !regexTest(SPECIAL_URL.source, result)) {
      if (result.indexOf('http') > -1) {
        result = result.slice(result.indexOf('http'));
      } else {
        result = urlJoin(baseUrl, result);
      }
    }
    
    return result;
  }

  /**
   * pdfl - 解析HTML获取列表数据
   */
  function pdfl(html, parse, listText, listUrl, baseUrl) {
    if (!html || !parse) return [];
    
    var elements = pdfa(html, parse);
    var results = [];
    
    for (var i = 0; i < elements.length; i++) {
      var itemHtml = elements[i];
      var title = pdfh(itemHtml, listText, baseUrl);
      var url = pd(itemHtml, listUrl, baseUrl);
      if (title || url) {
        results.push(title + '$' + url);
      }
    }
    
    return results;
  }

  /**
   * pjfh - 解析JSON获取单个值
   */
  function pjfh(json, parse, addUrl, baseUrl) {
    if (!json || !parse) return '';
    
    try {
      if (typeof json === 'string') {
        json = JSON.parse(json);
      }
    } catch(e) {
      console.log('[pjfh] JSON解析失败: ' + e.message);
      return '';
    }
    
    if (!parse.startsWith('$.')) parse = '$.' + parse;
    
    var result = '';
    var paths = parse.split('||');
    
    for (var i = 0; i < paths.length; i++) {
      var path = paths[i];
      var queryResult = jsonpath.query(json, path);
      result = Array.isArray(queryResult) ? (queryResult[0] || '') : (queryResult || '');
      if (addUrl && result && baseUrl) {
        result = urlJoin(baseUrl, result);
      }
      if (result) break;
    }
    
    return result;
  }

  /**
   * pj - 解析JSON并自动拼接URL
   */
  function pj(json, parse, baseUrl) {
    if (!baseUrl) {
      baseUrl = (typeof MY_URL !== 'undefined' && MY_URL) ? MY_URL : 
                (typeof HOST !== 'undefined' && HOST) ? HOST : '';
    }
    return pjfh(json, parse, true, baseUrl);
  }

  /**
   * pjfa - 解析JSON获取数组结果
   */
  function pjfa(json, parse) {
    if (!json || !parse) return [];
    
    try {
      if (typeof json === 'string') {
        json = JSON.parse(json);
      }
    } catch(e) {
      return [];
    }
    
    if (!parse.startsWith('$.')) parse = '$.' + parse;
    
    var result = jsonpath.query(json, parse);
    if (Array.isArray(result) && Array.isArray(result[0]) && result.length === 1) {
      return result[0];
    }
    
    return result || [];
  }

  /**
   * Jsoup 类 - 兼容原有接口
   */
  function Jsoup(MY_URL) {
    this.MY_URL = MY_URL || '';
    this.pdfh_html = '';
    this.pdfa_html = '';
  }
  
  Jsoup.prototype = {
    test: function(pattern, text) {
      return regexTest(pattern, text);
    },
    contains: function(text, match) {
      return contains(text, match);
    },
    parseHikerToJq: parseHikerToJq,
    getParseInfo: getParseInfo,
    reorderAdjacentLtAndGt: reorderAdjacentLtAndGt,
    parseText: function(text) {
      return cleanText(text);
    },
    pdfa: function(html, parse) {
      return pdfa(html, parse);
    },
    pdfl: function(html, parse, listText, listUrl, MY_URL) {
      return pdfl(html, parse, listText, listUrl, MY_URL || this.MY_URL);
    },
    pdfh: function(html, parse, baseUrl) {
      return pdfh(html, parse, baseUrl || this.MY_URL);
    },
    pd: function(html, parse, baseUrl) {
      return pd(html, parse, baseUrl || this.MY_URL);
    },
    pjfh: function(json, parse, addUrl) {
      return pjfh(json, parse, addUrl, this.MY_URL);
    },
    pj: function(json, parse) {
      return pj(json, parse, this.MY_URL);
    },
    pjfa: function(json, parse) {
      return pjfa(json, parse);
    },
    pq: function(html) {
      return load(html);
    }
  };

  // ============================================
  // 导出到全局
  // ============================================
  
  var exports = {
    // HTML解析
    pdfa: pdfa,
    pdfh: pdfh,
    pd: pd,
    pdfl: pdfl,
    load: load,
    
    // JSON解析
    pjfh: pjfh,
    pj: pj,
    pjfa: pjfa,
    jsonpath: jsonpath,
    
    // 工具函数
    urlJoin: urlJoin,
    cleanText: cleanText,
    
    // 类
    Jsoup: Jsoup,
    HtmlElement: HtmlElement,
    
    // 兼容别名
    pdfa_advanced: pdfa,
    pdfh_advanced: pdfh,
    pd_advanced: pd,
    pdfa_lite: pdfa,
    pdfh_lite: pdfh,
    pd_lite: pd
  };
  
  // 创建 jsp 对象
  var jsp = {
    pdfa: pdfa,
    pdfh: pdfh,
    pd: pd,
    pdfl: pdfl,
    pjfh: pjfh,
    pj: pj,
    pjfa: pjfa,
    Jsoup: Jsoup
  };
  
  // 设置到全局
  for (var key in exports) {
    global[key] = exports[key];
  }
  
  global.jsp = jsp;
  global.cheerio = { load: load };
  
  if (typeof globalThis !== 'undefined') {
    for (var key in exports) {
      globalThis[key] = exports[key];
    }
    globalThis.jsp = jsp;
    globalThis.cheerio = { load: load };
  }
  
  console.log('[统一解析器] HTML/JSON 解析器已加载');

})(typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : this));