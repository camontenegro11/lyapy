"""Quadratic program controller."""

from numpy import dot, identity, Inf, zeros
from numpy.linalg import norm

from ..lyapunov_functions import LearnedQuadraticControlLyapunovFunction
from .controller import Controller
from .util import solve_control_qp

class QPController(Controller):
    """Quadratic program controller.

    QP is

	  inf     1 / 2 * u'Pu + q'u + r + 1 / 2 * C * a'(P^-1)a * delta^2
	u, delta

	  s.t     a'u + b <= delta.

    If C is Inf, the slack, delta, is removed from the problem. Exception will
	then be raised if problem is infeasible.

    Let n be the number of states, m be the number of inputs.

    Attributes:
    Control task output, output: Output
    Input size, m: int
    Cost function Hessian, P: numpy array (n,) * float -> numpy array (m, m)
    Cost function linear term, q: numpy array (n,) * float -> numpy array (m,)
    Cost function scalar term, r: numpy array (n,) * float -> float
    Constraint function linear term, a: numpy array (n,) * float -> numpy array (m,)
    Constraint function scalar term, b: numpy array (n,) * float -> float
    Slack weight, C: float
    Slack, delta: float
    """

    def __init__(self, output, m, P=None, q=None, r=None, a=None, b=None, C=Inf):
        """Initialize a QPController object.

        Inputs:
        Control task output, output: Output
        Input size, m: int
        Cost function Hessian, P: numpy array (n,) * float -> numpy array (m, m)
        Cost function linear term, q: numpy array (n,) * float -> numpy array (m,)
        Cost function scalar term, r: numpy array (n,) * float -> float
        Constraint function linear term, a: numpy array (n,) * float -> numpy array (m,)
        Constraint function scalar term, b: numpy array (n,) * float -> float
        Slack weight, C: float
        """

        Controller.__init__(self, output)

        if P is None:
            P = lambda x, t: identity(m)
        if q is None:
            q = lambda x, t: zeros(m)
        if r is None:
            r = lambda x, t: 0
        if a is None:
            a = lambda x, t: zeros(m)
        if b is None:
            b = lambda x, t: 0

        self.m = m
        self.P, self.q, self.r = P, q, r
        self.a, self.b = a, b
        self.C = C
        self.delta = None

    def u(self, x, t):
        m = self.m
        P, q, r = self.P(x, t), self.q(x, t), self.r(x, t)
        a, b = self.a(x, t), self.b(x, t)
        C = self.C
        u_qp, self.delta = solve_control_qp(m, P, q, r, a, b, C)
        return u_qp

    def build_min_norm(quadratic_control_lyapunov_function, C=Inf):
        """Build a minimum norm controller for an affine dynamic output.

        QP is

          inf     1 / 2 * u'u + C * (decoupling)'(decoupling) * delta^2
        u, delta
          s.t     (decoupling)'u + drift <= -alpha * V + delta.

        If C is Inf, the slack, delta, is removed from the problem. Exception
        will then be raised if problem is infeasible.

        Outputs a QP Controller.

        Inputs:
        Quadratic CLF, quadratic_control_lyapunov_function: QuadraticControlLyapunovFunction
        Slack weight, C: float
        """

        affine_dynamic_output = quadratic_control_lyapunov_function.output
        m = affine_dynamic_output.G.shape[-1]
        a = quadratic_control_lyapunov_function.decoupling
        alpha = quadratic_control_lyapunov_function.alpha
        V = quadratic_control_lyapunov_function.V
        b = lambda x, t: quadratic_control_lyapunov_function.drift(x, t) + alpha * V(x, t)
        return QPController(affine_dynamic_output, m, a=a, b=b, C=C)

    def build_aug(nominal_controller, m, quadratic_control_lyapunov_function, a, b, C=Inf):
        """Build a minimum norm augmenting controller for an affine dynamic output. 

        QP is

          inf     1 / 2 * (u + u_c)'(u + u_c) + C * (V_decoupling + a)'(V_decoupling + a) * delta^2
        u, delta
          s.t     V_drift + V_decoupling * u_c + a'(u + u_c) <= -alpha * V + delta.

        If C is Inf, the slack, delta, is removed from the problem. Exception
        will then be raised if problem is infeasible.

        Outputs a QP Controller.

        Inputs:
        Nominal controller, nominal_controller: Controller
        Input size, m: int
        Quadratic CLF: quadratic_control_lyapunov_function: QuadraticControlLyapunovFunction
        Modeled constraint linear term, a: numpy array (n,) * float -> numpy array (m,)
        Modeled constraint scalar term, b: numpy array (n,) * float -> float
        Slack weight, C: float
        """

        learned_quadratic_control_lyapunov_function = LearnedQuadraticControlLyapunovFunction.build(quadratic_control_lyapunov_function, a, b)
        affine_dynamic_output = quadratic_control_lyapunov_function.output
        q = nominal_controller.u
        r = lambda x, t: (norm(q(x, t)) ** 2) / 2
        a = learned_quadratic_control_lyapunov_function.decoupling
        alpha = quadratic_control_lyapunov_function.alpha
        V = quadratic_control_lyapunov_function.V
        b = lambda x, t: learned_quadratic_control_lyapunov_function.drift(x, t) + dot(a(x, t), q(x, t)) + alpha * V(x, t)
        return QPController(affine_dynamic_output, m, q=q, r=r, a=a, b=b, C=C)
