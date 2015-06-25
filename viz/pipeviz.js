
// TODO Add a title bar for iframe (which node and which output of that node)
// TODO mousing through menu shouldn't dim the corresponding node
server = document.URL.split('/', 3).join('/');


function graphDraw(graph) {

    _graph = graph;
    invert_x_y = false;

    var IN_PROGRESS_COLOR = '#aaaaaa';
    var FAILURE_COLOR = '#ff9896';
    var COMPLETED_COLOR = '#98df8a';

    // UI constants
    var DIM_OPACITY = .2;
    var NEIGHBOR_OPACITY = .7;
    var SELECTED_OPACITY = .9;
    var DEFAULT_OPACITY = SELECTED_OPACITY;
    var SELECTED_LINK_OPACITY = .99;
    var DEFAULT_LINK_OPACITY = .4;
    var MOUSEOVER_TRANSITION_TIME = 100;
    var EXPAND_TRANSITION_TIME = 300;
    var SMALL_ICON_SIZE = 21;
    // var IFRAME_HEIGHT = 266;
    // var IFRAME_WIDTH = 466;
    var IFRAME_HEIGHT = 400;
    var IFRAME_WIDTH = 700;
    var TEXT_OFFSET = 15;
    var TEXT_ANGLE_SUPERNODE = -30;
    var TEXT_ANGLE_SUBNODE = -12;
    // var TEXT_ANGLE_SUPERNODE = 10;
    // var TEXT_ANGLE_SUBNODE = 30;
    var LEGEND_ITEM_HEIGHT; // set below after sizer()
    var LEGEND_PAD = 6;
    var ARROWHEAD_SIZE = 5;

    var NODESIZE = 12;
    var BORDER = .00;

    var h = 900,
        //w = 800;
        w = 1200;
    if (invert_x_y) {
        var tmp = h;
        h = w;
        w = tmp;
    }

    // Declarations
    var color, nstages, xscale, xgap;
    var istage, supernodesInStage, truex, border, yscale;
    var i, l;
    var svg, subnode_g, subnode_circle, subnode_text, subnode_text_shadow,
        subnode_text_fg, supernode_g, supernode_circle, supernode_plussign,
        singleton, multiparent;
    //var legend;

    ///////////////////////
    // Utility functions //
    ///////////////////////
    // via https://twitter.github.io/typeahead.js/examples/
    var substringMatcher = function(strs) {
      return function findMatches(q, cb) {
        var matches, substringRegex;

        // an array that will be populated with substring matches
        matches = [];

        // regex used to determine if a string contains the substring `q`
        substrRegex = new RegExp(q, 'i');

        // iterate through the pool of strings and for any string that
        // contains the substring `q`, add it to the `matches` array
        $.each(strs, function(i, str) {
          if (substrRegex.test(str)) {
            matches.push(str);
          }
        });

        console.log(matches);
        cb(matches);
      };
    };
    function assert(condition, message) {
        if (!condition) {
            throw message || "Assertion failed";
        }
    };
    function hide(d) {
        d._hidden = true;
    };
    function unhide(d) {
        d._hidden = false;
    };
    // function abbreviateText(str, threshold) {
    //     threshold = threshold || 200;
    //     if (str.length > threshold) {
    //         return str.substring(0, threshold) + "...";
    //     } else {
    //         return str;
    //     }
    // }
    function sizer(k) {
        return Math.sqrt(Math.sqrt(k+1)) * NODESIZE;
    }
    LEGEND_ITEM_HEIGHT = 2 * sizer(1.5);
    function mySlicer(arr, indices) {
        out = [];
        for (var i=0; i<indices.length; i++) {
            out.push(arr[indices[i]]);
        }
        return out;
    }
    $.ajaxSetup({
        timeout: 1000 * 60 // global AJAX timeout of 1 minute
    });


    // adapted from http://bl.ocks.org/mbostock/7555321
    function wrap(text, width) {
      text.each(function() {
        var text = d3.select(this);
        var words = text.text().split(/\s+/).reverse(),
            word,
            line = [],
            y = text.attr("y"),
            tspan = text.text(null).append("tspan").attr("x", 0).attr("y", y).attr("dy", "0em");
        while (word = words.pop()) {
          line.push(word);
          tspan.text(line.join(" "));
          if (tspan.node().getComputedTextLength() > width) {
            line.pop();
            tspan.text(line.join(" "));
            line = [word];
            tspan = text.append("tspan").attr("x", 0).attr("y", y).attr("dy", "1.1em").text(word);
          }
        }
      });
    }

    /**
     * Polls the status of each node (across all expansions) and adjusts the
     * visual representation accordingly.
     * Assumes the server will respond after a long delay (long polling).
     */
    function pollNodeStatuses(timeout) {
        $.get('/nodeStatuses', {"timeout": timeout}, function(result) {
            // assumes server will sleep before responding for a "long poll"
            subnode_text_shadow
                .style("stroke", function(d, i) {
                    d.completionStatus = result[i];
                    if (result[i] === 0) {
                        return IN_PROGRESS_COLOR;
                    } else if (result[i] === 1) {
                        return COMPLETED_COLOR;
                    } else if (result[i] === -1) {
                        return FAILURE_COLOR;
                    }
                });
            supernode_text_shadow
                .each(function(d_super) {
                    var foundProgress = false;
                    var foundCompleted = false;
                    var foundFailure = false;
                    d3.selectAll(d_super.subnode_elements)
                        .each(function(d_sub) {
                            if (d_sub.completionStatus === 0) {
                                foundProgress = true;
                            } else if (d_sub.completionStatus === 1) {
                                foundCompleted = true;
                            } else if (d_sub.completionStatus === -1) {
                                foundFailure = true;
                            }
                        });
                    d_super.strokeStyle = gradientMap[[foundProgress, foundCompleted, foundFailure]];
                })
                .style("stroke", function(d_super) { return d_super.strokeStyle; });
            pollNodeStatuses(3); // keep polling forever
        });

    }
    gradientMap = {};
    //    [progress, completed, failure]
    gradientMap[[true, true, true]] = 'url(#gradientProgressCompletedFailure)';
    gradientMap[[true, true, false]] = 'url(#gradientProgressCompleted)';
    gradientMap[[true, false, true]] = 'url(#gradientProgressFailure)';
    gradientMap[[false, true, true]] = 'url(#gradientCompletedFailure)';
    gradientMap[[true, false, false]] = IN_PROGRESS_COLOR;
    gradientMap[[false, true, false]] = COMPLETED_COLOR;
    gradientMap[[false, false, true]] = FAILURE_COLOR;

    /**
     * Compare two nodes to see the relationship between them.
     * The two nodes can be subnodes or supernodes (don't have to
     * be the same type)
     */
    function compare(d1, d2, same, neighbor, other) {
        assert(!d1.hidden);
        assert(!d2.hidden);
        var out;
        var i = (d1.type === 'super') ? d1.id : ("supernode" + d1.supernode);
        var j = (d2.type === 'super') ? d2.id : ("supernode" + d2.supernode);
        if (d1.id === d2.id) {
            out= same;
        } else if(superadjacency[i + "," + j] || superadjacency[j + "," + i]) {
            out = neighbor;
        } else if (( (d1.type === 'super') && (d2.type === 'sub') && (d1.subnodes.indexOf(d2.index) > -1)) ||
                    ( (d2.type === 'super') && (d1.type === 'sub') && (d2.subnodes.indexOf(d1.index) > -1))) {
            out = neighbor;
        } else {
            out = other;
        }
        return out;
    };

    ///////////
    // Setup //
    ///////////
    
    var states = ['Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California',
    'Colorado', 'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii',
    'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire',
    'New Jersey', 'New Mexico', 'New York', 'North Carolina', 'North Dakota',
    'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island',
    'South Carolina', 'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont',
    'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming'
    ]; 
    graph.subnodes.forEach(function(d, i) {
        d.children = [];
        if ((d.parameterization === null) || (d.parameterization === undefined)) {
            //d.descr = graph.supernodes[graph.reverse_mapping[i]].name;
            d.descr = d.name;
        } else {
            d.descr = d.parameterization.join(", ");
        }
        d.type = 'sub';
    });
    color = d3.scale.category10();

    nstages = d3.max(graph.supernodes, function(d) { return d.stage; });
    xscale = d3.scale.linear()
        .domain([-1, nstages+1])
        .range([BORDER*w, ((1-BORDER) - .2)*w]);

    xgap = (xscale(2) - xscale(1));

    for (var istage=0; istage<=nstages; istage++) {
        var supernodesInStage = graph.supernodes.filter(function(d) { return d.stage === istage; });
        var stageSize = supernodesInStage.length;
        var truex = xscale(istage);

        // TODO investigate other layouts
        //var border = BORDER + 6*BORDER*(istage % 2);
        var yscale;
        if (stageSize === 1) {
            yscale = function(x) { return h/2; };
        } else {
            yscale = d3.scale.linear()
                .domain([0, stageSize-1])
                .range([BORDER*8*h, (1-BORDER*8)*h]);
        }

        for (var jjj=0; jjj<stageSize; jjj++) {
            var stageOffset;
            if (istage % 2 === 0) {
                stageOffset = 0;
            } else {
                stageOffset = 0;
            }
            // } else {
            //     stageOffset = ((jjj/(stageSize-1))-.5) * (xgap*.75);
            //     console.log(stageOffset);
            // }
            s = supernodesInStage[jjj];
        //supernodesInStage.forEach(function(s) {
            s.type = 'super';
            s.descr = s.name;
            s.truey = s.y = yscale(s.height) + stageOffset;
            s.truex = s.x = truex;
            //s.truex = truex;
        };
        //});
    }

    // adjacency = {};
    superadjacency = {};
    for (i=0; i<graph.links.length; i++) {
        l = graph.links[i];
        l.source = graph.supernodes[l.supersource];
        l.target = graph.supernodes[l.supertarget];
        if (l.weight > 0) {
            // adjacency["subnode" + l.source + ",subnode" + l.target] = 1;
            superadjacency["supernode" + l.supersource + ",supernode" + l.supertarget] = 1;
        }
    }

    svg = d3.select(".canvas").append("svg")
            .attr("height", h*1.2)
            .attr("width", w);

    foreign = svg.append("foreignObject")
            .attr("width", 480)
            .attr("height", 500)
            .append("xhtml:body")
            .style("font", "14px 'Helvetica Neue'")
            .html('<div id="subjpicker" class="subjpickdiv"><form action="/changeSubject"><input class="typeahead" type="text" name="subj" placeholder="Subject" />  <input type="submit" value="Load" /></form></div>');

//     $.get('/getSubjects', function(results) {
//         console.log(results);
//         console.log(substringMatcher(results));
//         $('.typeahead').typeahead({
//             hint: true,
//             highlight: true,
//             minLength: 1
//         },
//         {
//             name: 'subjects',
//             source: substringMatcher(results)
//         }); 
//     });
    defs = svg.append('defs');
    arrowhead = defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('markerWidth', ARROWHEAD_SIZE*2)
        .attr('markerHeight', ARROWHEAD_SIZE)
        .attr('viewBox', '-6 -6 12 12')
        .attr('markerUnits', 'strokeWidth')
        .attr('refX', '5')
        .attr('refY', '0')
        .attr('orient', 'auto')
        .style('fill-opacity', 'inherit')
        .style('opacity', 'inherit')
        .style('stroke-opacity', 'inherit');

    /// make color gradients
    var bProgress, bCompleted, bFailure;
    var gradientName, gradientStopCtr, gradientCount;
    var boolList, nameList, colorList;
    var curBool, curName, curColor;
    nameList = ['Progress', 'Completed', 'Failure'];
    colorList = [IN_PROGRESS_COLOR, COMPLETED_COLOR, FAILURE_COLOR];
    var TRUTH_VALUES = [true, false];
    for (bP in TRUTH_VALUES) {
        for (bC in TRUTH_VALUES) {
            for (bF in TRUTH_VALUES) {
                bProgress = bP === "1";
                bCompleted = bC === "1";
                bFailure = bF === "1";
                gradientCount = bProgress + bCompleted + bFailure;
                if (gradientCount <= 1) {
                    continue;
                }
                gradient = defs.append('linearGradient')
                gradientName = 'gradient';
                gradientStopCtr = 0;
                boolList = [bProgress, bCompleted, bFailure];
                for (i=0 ; i<3 ; i++) {
                    curBool = boolList[i];
                    curName = nameList[i];
                    curColor = colorList[i];
                    if (curBool) {
                        gradientName += curName;
                        gradient.append('stop')
                            .attr('offset', gradientStopCtr * (100/(gradientCount-1)) + '%')
                            .attr('stop-color', curColor);
                        gradientStopCtr += 1;
                    }
                }
                gradient.attr('id', gradientName);
            }
        }
    }

    marker = arrowhead.append('polygon')
        .attr('points', '-2,0 -5,5 5,0 -5,-5');

    link = svg.selectAll(".link")
          .data(graph.links)
        .enter().append("line")
          .attr("class", "link")
          .attr('marker-end', 'url(#arrowhead)')
          .style("stroke-width", 3)
          .style("stroke-opacity", DEFAULT_LINK_OPACITY)
          .style("opacity", DEFAULT_LINK_OPACITY);

    ///////////////////////////////////////////////////////////////////////////
    // Initialize nodes

    // Initialize subnodes: each is a <g> w/ both circle and text
    subnode_g = svg.selectAll(".subnode")
          .data(graph.subnodes)
        .enter().append("g")
          .attr("class", "node subnode")
          .attr("visibility", "visible")
          .style("opacity", 0);

    subnode_circle = subnode_g.append("circle")
          .attr("r", function(d) { d.radius = NODESIZE; return d.radius; })
          .attr("id", function(d) { return d.id; })
          .style("fill", function(d) { return color(d.klass); });

    // Initialize text: container <g>, "shadow"/embossing, and foreground
    subnode_text = subnode_g
        .append("svg:g")
        .attr("class", "text-container")
        .attr("transform", function(d, i) {
            var vert_offset = NODESIZE * 0;
            return "translate(" + TEXT_OFFSET + "," + vert_offset + ")";
        });


    subnode_text_shadow = subnode_text.append("svg:text")
        .attr("class", function(d) { return d.id + "text" + " shadow labeltext"; })
        .text(function(d) { return d.descr; });

    subnode_text_fg = subnode_text.append("svg:text")
        .attr("class", function(d) { return d.id + "text" + " foreground labeltext"; })
        .text(function(d) { return d.descr; });

    // Initialize supernodes: each is a <g> w/both circle and [+]/[-] text
    // supernodes should go second so that they're on top (and clickable)
    supernode_g = svg.selectAll(".supernode")
        .data(graph.supernodes)
      .enter().append("g")
        .attr("class", "node supernode")
        .attr("visibility", "visible")
        .attr("transform", function(d) {
            if (invert_x_y) {
                return "translate(" + d.truey + "," + d.truex + ")";
            } else {
                return "translate(" + d.truex + "," + d.truey + ")";
            }
        })
        .style("opacity", DEFAULT_OPACITY);

    supernode_circle = supernode_g.append("circle")
        .attr("r", function(d) { d.radius = sizer(d.subnodes.length); return d.radius; })
        .style("fill", function(d) { return color(d.klass); });

    supernode_plussign = supernode_g.append("text")
        .attr("text-anchor", "middle")
        .text(function(d) { return d.subnodes.length > 0 ? "[+]" : ""; })
        .attr("dy", "0.5ex");

    supernode_text = supernode_g
        .append("svg:g")
        .attr("class", "text-container")
        .attr("transform", function(d, i) {
            var vert_offset = NODESIZE * 0;
            return "translate(" + TEXT_OFFSET + "," + vert_offset + ")";
        });

    supernode_text_shadow = supernode_text.append("svg:text")
        .attr("class", function(d) { return d.id + "text" + " shadow labeltext"; })
        .attr("text-anchor", "end")
        .text(function(d) { return (d.name === undefined) ? '' : abbreviateText(d.name); });

    supernode_text_fg = supernode_text.append("svg:text")
        .attr("class", function(d) { return d.id + "text" + " foreground labeltext"; })
        .attr("text-anchor", "end")
        .text(function(d) { return (d.name === undefined) ? '' : abbreviateText(d.name); });

    d3.selectAll(".labeltext")
        .call(wrap, 100);
    // Establish mappings between the supernodes and subnodes
    supernode_g.each(function(d_super, i) {
        d_super.subnode_elements = mySlicer(subnode_g[0], d_super.subnodes);
        // set all subnodes to be located at the same position as their supernode
        });

    subnode_g.each(function(d, i) {
        d.supernode_element = supernode_g[0][graph.reverse_mapping[i]];
        supernode_g.each(function(d_super, i) {
            d3.selectAll(d_super.subnode_elements)
                .style("pointer-events", "none")
                .each(function(d_sub) { hide(d_sub); });
        });
    });
    function moveSubnodesToSupernodes() {

        supernode_g.each(function(d_super, i) {
            d3.selectAll(d_super.subnode_elements)
                .attr("transform", function(d_sub) {
                    if (invert_x_y) {
                        return "translate(" + d_super.y + "," + d_super.truex + ")";
                    } else {
                        return "translate(" + d_super.truex + "," + d_super.y + ")";
                    }
                });
        });
    };

    //function showSingleSubnode(iterableName) {
    //var showSingleSubnode = function(iterableName) {
    showSingleSubnode = function(iterableName) {
        supernode_g
            .attr("visibility", "hidden")
            .each(function(d_super, i) {
                d3.selectAll(d_super.subnode_elements)
                    .filter(function(d_sub, i) {
                        return d_sub.descr === "_" + iterableName;
                    })
                    .style("opacity", 1)
                    .style("pointer-events", "all")
                    .each(function(d_sub) {
                        unhide(d_sub);
                        d_sub.descr = d_super.descr + " (" + d_sub.descr + ")";
                    });
            });
    };


    // Set up singleton supernodes to be their child nodes
    singleton = supernode_g.filter(function(d, i) {
        return (d.subnode_elements.length === 1);
    });
    multiparent = supernode_g
        .filter(function(d, i) {
            return (d.subnode_elements.length > 1);
        })
        .each(function(d, i) {
            d._collapsed = true;
        });

    singleton
        .attr("visibility", "hidden")
        .each(function(d_super, i) {
            d3.selectAll(d_super.subnode_elements)
                .style("opacity", 1)
                .style("pointer-events", "all")
                .each(function(d_sub) {
                    unhide(d_sub);
                    d_super.descr = d_sub.descr;
                    //d_sub.descr = d_super.descr + " (" + d_sub.descr + ")";
                });
        });

    ///////////////////////////////////////////////////////////////////////////
    // Initialize links

    d3.selectAll(".node")
        .on("mouseover", function(d_this) {
            d3.select(this).style('cursor', 'pointer');
            d3.select(this).style('stroke-width', '');
            var thisi = d_this.supernode || d_this.index;
            if (d_this.hidden) {
                return;
            }
            d3.selectAll(".node")
                .transition().duration(MOUSEOVER_TRANSITION_TIME)
                .style("opacity", function(d_other) {
                    if (d_other._hidden) {
                        return 0;
                    } else {
                        return compare(d_this, d_other,
                            SELECTED_OPACITY, NEIGHBOR_OPACITY, DIM_OPACITY);
                    }
                });
            d3.selectAll(".node > circle")
                .style("stroke-width", function(d_other, i_other) {
                    return compare(d_this, d_other, '4.5px', '2.5px', '2.5px');
                });
            // d3.selectAll(".labeltext")
            //     .text(function(d_other) { return compare(d_this, d_other, d_other.descr, d_other.descr, abbreviateText(d_other.descr)); });
            d3.selectAll(".link")
                .filter(function(d_link) { return d_link.supersource === thisi || d_link.supertarget === thisi; })
                .transition().duration(MOUSEOVER_TRANSITION_TIME)
                .style("stroke-opacity", SELECTED_LINK_OPACITY)
                .style("opacity", SELECTED_LINK_OPACITY);
        })
        .on("mouseout", function(d_this) {
            d3.select(this).style('cursor', 'default');
            if (d_this.hidden) {
                return;
            }
            d3.selectAll(".node")
                .filter(function(d) { return !d._hidden; })
                .transition().duration(MOUSEOVER_TRANSITION_TIME)
                .style("opacity", SELECTED_OPACITY);
            d3.selectAll(".node > circle")
                .style("stroke-width", function(d_other, i_other) {
                    return compare(d_this, d_other, '2.5px', '2.5px', '2.5px');
                });
            // d3.selectAll(".labeltext")
            //     .text(function(d_other) { return abbreviateText(d_other.descr); });
            d3.selectAll(".link")
                .transition().duration(MOUSEOVER_TRANSITION_TIME)
                .style("opacity", DEFAULT_LINK_OPACITY);
        });

    multiparent
        .on("click", function(d_super, i_super) {
            // TODO clean this up
            if (d_super._collapsed) {
                d_super._collapsed = false;
                d3.select(this).select('text')
                    .text('[-]');
                d3.selectAll(d_super.subnode_elements)
                        .each(function(d_sub) { unhide(d_sub); })
                        .style("pointer-events", "all")
                    .transition().duration(EXPAND_TRANSITION_TIME)
                        .style("opacity", 1)
                        .attr("transform", function(d_sub, i_sub) {
                            var offset = (d_super.subnode_elements.length - 1)/2;
                            // var dx = d_super.truex + xgap/2;
                            // var dy = d_super.y + (i_sub - offset) * 30;
                            var dy = d_super.y + xgap/2;// + (i_sub - offset)*30;
                            var dx = d_super.x + (i_sub - offset) * 30;
                            if (invert_x_y) {
                                return "translate(" + dy + "," + dx + ")";
                            } else {
                                return "translate(" + dx + "," + dy + ")";
                            }
                        });
            } else {
                d_super._collapsed = true;
                d3.select(this).select('text')
                    .text('[+]');
                d3.selectAll(d_super.subnode_elements)
                        .each(function(d_sub) { hide(d_sub); })
                        .style("pointer-events", "none")
                    .transition().duration(EXPAND_TRANSITION_TIME)
                        .style("opacity", 0)
                        .attr("transform", function(d_sub, i_sub) {
                            var dx = d_super.truex;
                            var dy = d_super.y;
                            if (invert_x_y) {
                                return "translate(" + dy + "," + dx + ")";
                            } else {
                                return "translate(" + dx + "," + dy + ")";
                            }

                        });
            }
        });

    graph.supernodes.forEach(function(d) {
        d.x = d.truex;
        d.y = d.truey;
    });

    subnode_circle
        .on("click", function(d_subnode, i_subnode) {
            if (d_subnode.menu && (d_subnode.menu !== undefined)) {
                // TODO unify window-closing code with clicking on X button below
                d_subnode.menu.remove();
                d_subnode.menu = false;
            } else {
                var circle = this;
                var color = d3.rgb(d3.select(circle).style('fill'));
                var loc = d3.transform(d3.select(circle.parentNode).attr("transform")).translate
                // TODO dim all other nodes
                $.post('/getOutputInfo', {"index": i_subnode}, function(result) {
                    var _menu = d3.select(".canvas").append('ul')
                            .attr('nodeindex', i_subnode)
                            .attr('class', 'textmenu')
                            .style("left", (loc[0]+25) + "px")
                            .style("top", (loc[1]+20) + "px");
                    d_subnode.menu = _menu;
                    // TODO try using jquery ui menu
                    var menuData;
                    if (result.aggregate && (result.aggregate !== undefined)) {
                        _result = result;
                        menuData = $.map(result.data, function(d_result) {
                            return d_result;
                        });
                    } else {
                        menuData = result;
                    }
                    var _menuItems = _menu.selectAll('li')
                            .data(menuData)
                          .enter().append('li')
                            .html(function(d_item) {
                                var completion_pct_str = '';
                                var completion = d_item.completion_fraction;
                                if ((completion !== undefined) && (d_item.name !== 'Command line')) {
                                    completion_pct_str = ' (' + (completion*100).toFixed(1) + '%)';
                                }
                                var type;
                                if (d_item.type === 'string') {
                                    type = 'fa-align-justify';
                                } else if (d_item.type === 'file') {
                                    if (d_item.numeric !== 'undefined') {
                                        type = 'fa-bar-chart-o';
                                    } else {
                                        type = 'fa-file-image-o';
                                    }
                                }
                                return '<i class="fa ' + type + ' fa-fw"></i>&nbsp; ' + d_item.name + completion_pct_str;
                            })
                            .style('border-bottom', '1px solid ' + color.toString())
                            .style('padding', '3px')
                            .style('background-color', function(d_item) {
                                return color.brighter(2);
                            })
                            .style('text-align', function(d_item) {
                                if (d_item.type === 'close') {
                                    return 'center';
                                } else {
                                    return 'left';
                                }
                            })
                            .on("mouseover", function(d_item) {
                                d3.select(this)
                                    .style('background-color',color.brighter(1))
                                    .style('cursor', 'pointer');
                            })
                            .on("mouseout", function(d_item) {
                                d3.select(this)
                                    .style('background-color',color.brighter(2))
                                    .style('cursor', 'default');
                            })
                            .on("click", function(d_item) {
                                console.log(d_item);
                                _mymyitem = d_item;
                                if (d_item.type === 'string') {
                                    // TODO make a text box here instead of alert
                                    console.log(d_item.value);
                                    window.alert(d_item.value + "\n\n(Also printed to console)");
                                } else if (d_item.type === 'file') {
                                    var popupdiv = d3.select('.canvas').append('div')
                                        .attr('class', 'popup')
                                        .style('width', IFRAME_WIDTH + 'px')
                                        .style('height', IFRAME_HEIGHT + 'px')
                                        .style('opacity', .96)
                                        .on("mouseover", function(d) {
                                            d3.select(this).style('cursor', 'move');
                                        })
                                        .on("mouseout", function(d) {
                                            d3.select(this).style('cursor', 'default');
                                        });
                                    $('.popup').draggable().resizable();
                                    var popupClose = popupdiv.append('img')
                                        .attr('id', 'popupClose')
                                        .attr('src', 'closebutton.png')
                                        .style('margin', 'auto')
                                        .style('position', 'absolute')
                                        .style('left', '-21px') // half its size
                                        .style('top', '-21px')
                                        // .style('left', IFRAME_WIDTH +'px')
                                        // .style('top', IFRAME_HEIGHT + 'px')
                                        .on("mouseover", function(d) {
                                            d3.select(this).style('cursor', 'pointer');
                                        })
                                        .on("mouseout", function(d) {
                                            d3.select(this).style('cursor', 'default');
                                        })
                                        .on("click", function(d) {
                                            d3.select(this.parentNode).remove();
                                        });
                                    if (d_item.numeric && (d_item.numeric !== undefined)) {
                                        popupdiv.style('background-color', '#eee');
                                        console.log(d_item.outliersubj);
                                        nv.addGraph(function() {
                                            var chart = nv.models.discreteBarChart()
                                                .x(function(d) { return d.x; })
                                                .y(function(d) { return d.y; })
                                                .staggerLabels(false)
                                                .tooltips(true)
                                                .showValues(false)
                                                .color(function(d) { return '#1f77b4'; })
                                                .duration(1);

                                            popupdiv.append('svg')
                                                .style('width', IFRAME_WIDTH + 'px')
                                                .style('height', IFRAME_HEIGHT + 'px')
                                                .datum([{'key': 'Histogram', 'values': d_item.histogram}])
                                                .call(chart);
                                            nv.utils.windowResize(chart.update);
                                            return chart;
                                        });
                                    } else {
                                        if (d_item.mimetype === 'application/text') {
                                            $.post('/retrieveFile?filename='+filename, function(res) {
                                                $('.popup').innerHTML = '<pre>' + res + '</pre>';
                                            });
                                        } else if (d_item.mimetype === 'application/x-nifti') {
                                            // create a slicedrop iframe
                                            // TODO use jquery ui Dialog here instead
                                            var filename = d_item.value;
                                            var url = 'http://slicedrop.com/?' + server + '/retrieveFile?filename=' + filename;
                                            //var url = server + '/queryFileType?filename=' + filename;
                                            console.log("Displaying file:\n" + filename);
                                            var sdFrame = popupdiv.append('iframe')
                                                .attr('id', 'vizFrame')
                                                .attr('width', '86%')
                                                .style('height', '85%')
                                                .style('margin', 'auto')
                                                .style('margin-top', '3%')
                                                .style('opacity', 1)
                                                .attr('src', url);
                                        }
                                    }
                                }
                            });
                var _menuSize = _menu[0][0].offsetWidth;
                var _menuClose = d3.select('.canvas').append('img')
                    .attr('class', 'textmenu menuclose')
                    .style("left", (loc[0]+25 + _menuSize - SMALL_ICON_SIZE/2) + "px")
                    .style("top", (loc[1]+20 - SMALL_ICON_SIZE/2) + "px")
                    .attr('src', 'closebutton_small.png')
                    .on("mouseover", function(d) {
                        d3.select(this).style('cursor', 'pointer');
                    })
                    .on("mouseout", function(d) {
                        d3.select(this).style('cursor', 'default');
                    })
                    .on("click", function(d) {
                        // TODO unify window-closing code with clicking on node above
                        d3.select('.textmenu[nodeindex="'+i_subnode+'"]').remove();
                        d3.select(this).remove();
                    });
                });
            }
        });

    var charge = -6500;
    force = d3.layout.force()
        .gravity(.4)
        .friction(0.9)
        .charge(charge)
        .size([w*0.9, h])
        .links(graph.links)
        .nodes(graph.supernodes)
        .start();

    force.on("tick", function(e) {
        var kx = 8.2 * e.alpha;
        var ky = 0.04 * e.alpha;
        force.charge(charge);
        graph.supernodes.forEach(function(d, i) {
            d.x += (d.truex - d.x) * kx;
            d.y += (d.truey - d.y) * ky;


        });
    });

    //for (var i=0; i<10000; i++) {
    for (var i=0; i<10000; i++) {
    //while(true) {
         force.tick(); 
    supernode_g
        .attr("transform", function(d) {
            if (invert_x_y) {
                return  "translate(" + d.y + "," + d.truex + ")";
            } else {
                return "translate(" + d.truex + "," + d.y + ")";
            }
        });
    }

    force.stop();
    link.each(function(d) {
        var xStart = d.source.truex;
        var yStart = d.source.y;
        var xEnd = d.target.truex;
        var yEnd = d.target.y;

        var dx = xEnd - xStart;
        var dy = yEnd - yStart;
        var theta = Math.atan(dy/dx);
        d.x1 = xStart + d.source.radius * Math.cos(theta);
        d.x2 = xEnd - d.target.radius * Math.cos(theta);
        d.y1 = yStart + d.source.radius * Math.sin(theta);
        d.y2 = yEnd - d.target.radius * Math.sin(theta);
    });
    if (invert_x_y) {
        link.attr("y1", function(d) { return d.x1; })
            .attr("x1", function(d) { return d.y1; })
            .attr("y2", function(d) { return d.x2; })
            .attr("x2", function(d) { return d.y2; });
    } else {
        link.attr("x1", function(d) { return d.x1; })
            .attr("y1", function(d) { return d.y1; })
            .attr("x2", function(d) { return d.x2; })
            .attr("y2", function(d) { return d.y2; });
    }
    supernode_g
        .attr("transform", function(d) {
            if (invert_x_y) {
                return  "translate(" + d.y + "," + d.truex + ")";
            } else {
                return "translate(" + d.truex + "," + d.y + ")";
            }
        });


    var legendExpanded = true;
    legend_svg = d3.select(".legend-container").append("svg")
            .attr("class", "legendsvg");

    legend = legend_svg.append("g")
        .attr("class", "legend")
        .style("margin-right", "auto")
        .style("margin-left", "0");
        //.attr("transform", "translate(" + h*.65 + "," + w*.8 + ")");
        //.attr("preserveAspectRatio", "xMaxYMax meet");

    legend_items = legend.selectAll(".legenditem")
            .data(graph.klasses)
          .enter().append("g")
            .attr("class", "legenditem")
            .attr("transform", function(d, i) {
                return "translate(0," + (i+1) * LEGEND_ITEM_HEIGHT + ")";
            });

    legend_circles = legend_items.append("circle")
        .attr("r", sizer(.5))
        .style("fill", function(d, i) { return color(i); });
    legend_labels = legend_items.append("text")
        .text(function(d) { return d; })
        .style("font-size", "0.85em")
        .attr("transform", "translate(" + TEXT_OFFSET + ", 0)");

    // TODO use better system than unicode arrows: can't use icons in svg text,
    // but maybe fix/control width of arrow better?
    legend_label = legend.append("text")
        .text("▼ Legend")
        .attr("class", "legend-title")
        .attr("text-anchor", "middle")
        .on("mouseover", function(d) {
            d3.select(this).style('cursor', 'pointer');
        })
        .on("mouseout", function(d_this) {
            d3.select(this).style('cursor', 'default');
        })
        .on("click", function(d) {
            if (legendExpanded) {
                var height = legendTitleBox.height + 2*LEGEND_PAD;
                legend_svg.transition().duration(MOUSEOVER_TRANSITION_TIME).attr("height", height + "px");
                legend_outline.transition().duration(MOUSEOVER_TRANSITION_TIME).attr("height", height + "px");
                d3.select(this).text("▶ Legend");
                legendExpanded = false;
            } else {
                legend_svg.transition().duration(MOUSEOVER_TRANSITION_TIME).attr("height", legendHeight);
                legend_outline.transition().duration(MOUSEOVER_TRANSITION_TIME).attr("height", legendHeight);
                d3.select(this).text("▼ Legend");
                legendExpanded = true;
            }
        });

    var legendTitleBox = legend_label[0][0].getBBox();
    var fullLegendBox = legend[0][0].getBBox();

    var legendWidth, legendHeight;
    legendWidth = fullLegendBox.width + 2*LEGEND_PAD;
    legendHeight = fullLegendBox.height + 2*LEGEND_PAD;

    legend_outline = legend.append("rect")
        .attr("x", fullLegendBox.x - LEGEND_PAD)
        .attr("y", fullLegendBox.y - LEGEND_PAD)
        .attr("width", legendWidth)
        .attr("height", legendHeight)
        .attr("rx", "10px")
        .attr("ry", "10px")
        .style("-webkit-svg-shadow", "0 0 7px")
        .style("stroke", "#7f7f7f")
        .style("stroke-width", "2px")
        .style('fill-opacity', 1)
        .style("fill", "#f2f2f2");

    var legendMove = $('.legenditem').detach();
    $('.legend').append(legendMove);
    legendMove = $('.legend-title');
    $('.legend').append(legendMove);
    legend_svg.attr('width', legendWidth).attr('height', legendHeight);
    legend.attr('width', legendWidth).attr('height', legendHeight);
    d3.select('.legend-container')
        .style('width', legendWidth)
        .style('height', legendHeight);
    legend.attr('transform', 'translate(' + (LEGEND_PAD-fullLegendBox.x) + ',' + (LEGEND_PAD-fullLegendBox.y) + ')');
    moveSubnodesToSupernodes();
    //pollNodeStatuses(0); // keep polling forever
};
$(document).ready(function() {
    $.post('/getGraphJSON', graphDraw);
});
